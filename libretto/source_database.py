"""
SourceDatabase module for managing patient and note reading, insertions, and deletions.
"""

from typing import List, Optional, Set, Any, Dict, Union, Tuple, TypedDict, Literal
import json
import sqlalchemy as sa
from sqlalchemy import Table, Column, String, MetaData, insert, delete, URL
from sqlalchemy.engine import Engine, Result, create_engine
from sqlalchemy.sql import text, select, distinct

from .types import Patient, Note, ExtractionSpec
from .json_sanitize import safe_load_json
from pathlib import Path

# Default queries
DEFAULT_NOTE_METADATA_QUERY = "SELECT patients.id AS patient_id, notes.id AS note_id, notes.date AS note_date, patients.metadata AS patient_metadata, notes.metadata AS note_metadata\nFROM patients LEFT JOIN notes ON patients.id = notes.patient_id"
DEFAULT_NOTE_TEXT_QUERY = "SELECT id AS note_id, patient_id AS patient_id, note_text FROM notes"

def _resolve_query(source: dict, config_dir: Optional[Path] = None) -> str:
    """Resolve a SQL string from a dict with query_string or query_file."""
    if "query_string" in source:
        return source["query_string"]
    if "query_file" in source:
        query_path = Path(source["query_file"])
        if config_dir and not query_path.is_absolute():
            query_path = config_dir / query_path
        return query_path.read_text(encoding="utf-8").strip()
    raise ValueError("Query source must have 'query_string' or 'query_file'")


class MetadataFilter(TypedDict):
    """Filter for patient metadata fields.

    Attributes:
        field: Dot-notation path to metadata field (e.g. "demographics.age")
        operator: Comparison operator to apply
        value: Value to compare against (ignored for "exists" operator)
    """
    field: str
    operator: Literal["eq", "contains", "lt", "gt", "lte", "gte", "exists"]
    value: Any


class SourceDatabase:
    """Manages SQLAlchemy connection and retrieves patients and notes based on extraction specs."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        **connection_params
    ):
        """
        Initialize with either a connection string, pre-built engine, or connection parameters.

        Args:
            connection_string: SQLAlchemy connection string (e.g., 'postgresql://user:pass@host:port/db')
            **connection_params: Connection parameters including:
                - drivername: Database driver (e.g., 'postgresql', 'mysql', 'sqlite')
                - host: Database host
                - port: Database port
                - username: Database username
                - password: Database password
                - database: Database name
                - Additional engine creation parameters
        """
        if connection_string is not None:
            # Create engine from connection string
            self.connection_string = connection_string
            self.engine = self._create_engine_from_string(connection_string)
        elif connection_params:
            # Create engine from connection parameters
            self.connection_string, self.engine = self._create_engine_from_params(**connection_params)
        else:
            raise ValueError(
                "Must provide either 'engine', 'connection_string', or connection parameters "
                "(drivername, host, etc.)"
            )

    def _create_engine_from_string(self, connection_string: str) -> Engine:
        """Create SQLAlchemy engine from connection string."""
        return create_engine(connection_string)

    def _create_engine_from_params(self, **connection_params) -> Tuple[str, Engine]:
        """
        Create SQLAlchemy engine from connection parameters.

        Args:
            **connection_params: Connection parameters including:
                - drivername: Database driver (required, e.g., 'postgresql', 'mysql', 'sqlite')
                - host: Database host
                - port: Database port
                - username: Database username
                - password: Database password
                - database: Database name
                - Additional parameters are passed to create_engine()

        Returns:
            SQLAlchemy Engine instance
        """
        # Separate URL parameters from engine parameters
        url_params = {}
        engine_params = {}

        # URL construction parameters
        url_param_names = {'drivername', 'host', 'port', 'username', 'password', 'database'}

        for key, value in connection_params.items():
            if key in url_param_names:
                url_params[key] = value
            else:
                engine_params[key] = value

        if 'drivername' not in url_params:
            raise ValueError("'drivername' parameter is required (e.g., 'postgresql', 'mysql', 'sqlite')")

        # Create URL object
        url = URL.create(**url_params)

        # Create and return engine
        return str(url), create_engine(url, **engine_params)

    def _validate_query_columns(self, result: Result, expected_columns: Set[str], query_type: str) -> None:
        """Validate that query result has expected columns."""
        actual_columns = set(result.keys())
        if not expected_columns.issubset(actual_columns):
            missing_columns = expected_columns - actual_columns
            raise ValueError(
                f"{query_type} query must return columns: {sorted(expected_columns)}. "
                f"Missing columns: {sorted(missing_columns)}. "
                f"Actual columns: {sorted(actual_columns)}"
            )

    def _load_metadata_cte(self, spec: ExtractionSpec, config_dir: Optional[str] = None):
        """Create a metadata CTE from the extraction spec."""
        source_notes = spec.get("source_notes")

        if source_notes is not None:
            if "query_string" in source_notes or "query_file" in source_notes:
                # Single query with all columns
                query_str = _resolve_query(source_notes, config_dir)
                return text(query_str).columns(
                    patient_id=String,
                    note_id=String,
                    patient_metadata=String,
                    note_metadata=String,
                    note_date=String,
                    note_text=String,
                ).cte("metadata_cte")
            else:
                # Separate metadata query
                metadata_src = source_notes.get("metadata")
                if not metadata_src:
                    raise ValueError(
                        "source_notes must have either 'query_string'/'query_file', "
                        "or both 'metadata' and 'note_text' sub-objects"
                    )
                query_str = _resolve_query(metadata_src, config_dir)
                return text(query_str).columns(
                    patient_id=String,
                    note_id=String,
                    patient_metadata=String,
                    note_metadata=String,
                    note_date=String,
                ).cte("metadata_cte")
        elif spec.get("note_metadata_query"):
            # Legacy top-level query
            query_str = spec["note_metadata_query"]
            return text(query_str).columns(
                patient_id=String,
                note_id=String,
                patient_metadata=String,
                note_metadata=String,
                note_date=String,
            ).cte("metadata_cte")
        else:
            raise ValueError(
                "Config must include 'source_notes' or 'note_metadata_query'"
            )

    def _load_text_cte(self, spec: ExtractionSpec, config_dir: Optional[str] = None):
        """Create a text CTE from the extraction spec."""
        source_notes = spec.get("source_notes")

        if source_notes is not None:
            if "query_string" in source_notes or "query_file" in source_notes:
                # Single query already includes text, no separate CTE needed
                return None
            else:
                # Separate text query
                note_text_src = source_notes.get("note_text")
                if not note_text_src:
                    raise ValueError(
                        "source_notes must have both 'metadata' and 'note_text' sub-objects"
                    )
                query_str = _resolve_query(note_text_src, config_dir)
                return text(query_str).columns(
                    patient_id=String,
                    note_id=String,
                    note_text=String,
                ).cte("text_cte")
        elif spec.get("note_text_query"):
            # Legacy top-level query
            query_str = spec["note_text_query"]
            return text(query_str).columns(
                patient_id=String,
                note_id=String,
                note_text=String,
            ).cte("text_cte")
        else:
            return None

    def get_note_metadata(self, spec: ExtractionSpec, patient_ids: Optional[List[str]] = None, config_dir: Optional[str] = None, counts_only: bool = False) -> List[Patient]:
        """
        Return a list of patient objects with note metadata but no note text.

        Args:
            spec: ExtractionSpec containing the note_metadata_query
            patient_ids: Optional list of patient IDs to filter by
            config_dir: Directory containing the config file, used to
                resolve relative paths to query files
            counts_only: If True, return only note counts instead of note arrays

        Returns:
            List of Patient objects with notes containing metadata but no note_text,
            or with note_count containing the count if counts_only=True
        """
        metadata_cte = self._load_metadata_cte(spec, config_dir)

        if counts_only:
            # Return aggregated counts per patient
            query = select(
                metadata_cte.c.patient_id,
                metadata_cte.c.patient_metadata,
                sa.func.count(distinct(metadata_cte.c.note_id)).label("note_count"),
                sa.func.max(distinct(metadata_cte.c.note_date)).label("latest_note_date"),
                sa.func.min(distinct(metadata_cte.c.note_date)).label("earliest_note_date")
            ).group_by(
                metadata_cte.c.patient_id,
                metadata_cte.c.patient_metadata
            )
        else:
            query = select(
                metadata_cte.c.patient_id,
                metadata_cte.c.note_id,
                metadata_cte.c.patient_metadata,
                metadata_cte.c.note_metadata,
                metadata_cte.c.note_date
            )

        if patient_ids:
            query = query.where(metadata_cte.c.patient_id.in_(patient_ids))

        with self.engine.connect() as conn:
            result = conn.execute(query)
            notes = [dict(row._mapping) for row in result]

        if counts_only:
            # When counts_only=True, the query returns patient_id, patient_metadata, note_count
            return [
                {
                    "id": row["patient_id"],
                    "metadata": safe_load_json(row["patient_metadata"]),
                    "note_count": row["note_count"],
                    "earliest_note_date": row["earliest_note_date"],
                    "latest_note_date": row["latest_note_date"]
                }
                for row in notes
            ]
        else:
            # Group by patient_id when returning full note metadata
            patients_data: Dict[str, Dict[str, Any]] = {}
            for row in notes:
                if not row["note_id"]: continue
                patient_id = row["patient_id"]
                if patient_id not in patients_data:
                    patients_data[patient_id] = Patient.from_database_value(dict(
                        id=patient_id,
                        metadata=row["patient_metadata"],
                        notes=[],
                        note_count=0,
                        earliest_note_date=None,
                        latest_note_date=None
                    ))

                # Create note with metadata but no text
                note = Note.from_database_value(dict(
                    id=row["note_id"],
                    note_text=None,  # Explicitly set to None for metadata-only
                    date=row.get("note_date"),
                    metadata=row.get("note_metadata")
                ))
                pt = patients_data[patient_id]
                pt["notes"].append(note)
                pt["note_count"] += 1
                pt["earliest_note_date"] = note["date"] if pt["earliest_note_date"] is None else min(pt["earliest_note_date"], note["date"])
                pt["latest_note_date"] = note["date"] if pt["latest_note_date"] is None else max(pt["latest_note_date"], note["date"])

            return list(patients_data.values())

    def get_notes(self, spec: ExtractionSpec, patient_ids: Optional[List[str]] = None, config_dir: Optional[str] = None, note_limit: Optional[int] = None) -> List[Patient]:
        """
        Return a list of Patient objects with note text populated.

        Uses both note_metadata_query and note_text_query, combining them via CTEs.

        Supports three config formats (checked in order):
        1. source_notes.query_string / source_notes.query_file
                Single query returning all columns (patient_id, note_id,
                patient_metadata, note_metadata, note_text).
        2. source_notes.metadata + source_notes.note_text
                Two sub-queries joined via CTEs. Each sub-object must have
                query_string or query_file.
        3. note_metadata_query + note_text_query (legacy top-level strings)

        Args:
            spec: ExtractionSpec containing both queries
            patient_ids: Optional list of patient IDs to filter by
            config_dir: Directory containing the config file, used to
                resolve relative paths to query files
            note_limit: Maximum number of notes to retrieve (by default 
                all are retrieved)

        Returns:
            List of Patient objects with full note data including text
        """
        metadata_cte = self._load_metadata_cte(spec, config_dir)
        text_cte = self._load_text_cte(spec, config_dir)

        if text_cte is not None:
            # Join metadata and text CTEs
            query = select(
                metadata_cte.c.patient_id,
                metadata_cte.c.note_id,
                metadata_cte.c.patient_metadata,
                metadata_cte.c.note_metadata,
                metadata_cte.c.note_date,
                text_cte.c.note_text,
            ).select_from(
                metadata_cte.join(
                    text_cte,
                    sa.and_(
                        metadata_cte.c.patient_id == text_cte.c.patient_id,
                        metadata_cte.c.note_id == text_cte.c.note_id,
                    ),
                )
            )
        else:
            # Single query already has text column
            query = select(
                metadata_cte.c.patient_id,
                metadata_cte.c.note_id,
                metadata_cte.c.patient_metadata,
                metadata_cte.c.note_metadata,
                metadata_cte.c.note_date,
                metadata_cte.c.note_text,
            )

        if patient_ids:
            query = query.where(metadata_cte.c.patient_id.in_(patient_ids))

        if note_limit is not None:
            query = query.limit(note_limit)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            notes = [dict(row._mapping) for row in result]

        patients_data: Dict[str, Dict[str, Any]] = {}
        for row in notes:
            if not row["note_id"]: continue
            patient_id = row["patient_id"]
            if patient_id not in patients_data:
                patients_data[patient_id] = Patient.from_database_value(dict(
                    id=patient_id,
                    metadata=row["patient_metadata"],
                    notes=[],
                    note_count=0,
                    earliest_note_date=None,
                    latest_note_date=None
                ))

            # Create note with metadata but no text
            note = Note.from_database_value(dict(
                id=row["note_id"],
                note_text=row["note_text"],
                date=row.get("note_date"),
                metadata=row.get("note_metadata")
            ))
            pt = patients_data[patient_id]
            pt["notes"].append(note)
            pt["note_count"] += 1
            pt["earliest_note_date"] = note["date"] if pt["earliest_note_date"] is None else min(pt["earliest_note_date"], note["date"])
            pt["latest_note_date"] = note["date"] if pt["latest_note_date"] is None else max(pt["latest_note_date"], note["date"])

        return list(patients_data.values())

    def get_patients_with_metadata_filters(self, spec: ExtractionSpec, filters: List[MetadataFilter], config_dir: Optional[str] = None) -> List[str]:
        """
        Filter patients by metadata field values using application-level filtering.

        Args:
            spec: ExtractionSpec containing the note_metadata_query
            filters: List of MetadataFilter dicts
            config_dir: Directory containing the config file

        Returns:
            List of patient IDs that match all metadata filters (AND logic)
        """
        if not filters:
            return []

        # Get all patients with metadata (counts_only for efficiency)
        patients = self.get_note_metadata(spec, patient_ids=None, config_dir=config_dir, counts_only=True)

        # Apply filters to each patient
        matching_patient_ids = []
        for patient in patients:
            metadata = patient.get("metadata", {})
            if self._evaluate_metadata_filters(metadata, filters):
                matching_patient_ids.append(patient["id"])

        return matching_patient_ids

    def _evaluate_metadata_filters(self, metadata: Dict[str, Any], filters: List[MetadataFilter]) -> bool:
        """
        Evaluate whether patient metadata matches all filters (AND logic).

        Args:
            metadata: Patient metadata dict
            filters: List of MetadataFilter dicts

        Returns:
            True if all filters match, False otherwise
        """
        for filter_spec in filters:
            if not self._evaluate_single_metadata_filter(metadata, filter_spec):
                return False
        return True

    def _evaluate_single_metadata_filter(self, metadata: Dict[str, Any], filter_spec: MetadataFilter) -> bool:
        """
        Evaluate a single metadata filter against patient metadata.

        Args:
            metadata: Patient metadata dict
            filter_spec: Single MetadataFilter dict

        Returns:
            True if filter matches, False otherwise
        """
        field = filter_spec["field"]
        operator = filter_spec["operator"]
        expected_value = filter_spec["value"]

        # Navigate dot notation paths (e.g., "demographics.age")
        try:
            actual_value = self._get_nested_value(metadata, field)
        except (KeyError, TypeError):
            # Field doesn't exist or path is invalid
            return operator == "exists" and expected_value is None

        # Handle "exists" operator - just check if field is present
        if operator == "exists":
            return True  # We got here, so field exists

        # Handle comparison operators
        if operator == "eq":
            return self._values_equal(actual_value, expected_value)
        elif operator == "contains":
            return self._value_contains(actual_value, expected_value)
        elif operator in ["lt", "gt", "lte", "gte"]:
            return self._compare_numeric_values(actual_value, expected_value, operator)
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get value from nested dict using dot notation path.

        Args:
            data: Dictionary to navigate
            path: Dot-separated path (e.g., "demographics.age")

        Returns:
            Value at the specified path

        Raises:
            KeyError: If path doesn't exist
            TypeError: If intermediate value is not a dict
        """
        parts = path.split(".")
        current = data

        for part in parts:
            if not isinstance(current, dict):
                raise TypeError(f"Cannot navigate path '{path}': intermediate value is not a dict")
            if part not in current:
                raise KeyError(f"Path '{path}' not found")
            current = current[part]

        return current

    def _values_equal(self, actual: Any, expected: Any) -> bool:
        """Compare two values for equality, handling type coercion."""
        # Handle None values
        if actual is None or expected is None:
            return actual == expected

        # Try direct equality first
        if actual == expected:
            return True

        # Try string comparison (case-insensitive)
        try:
            return str(actual).lower() == str(expected).lower()
        except:
            return False

    def _value_contains(self, actual: Any, expected: Any) -> bool:
        """Check if actual value contains expected value."""
        if actual is None or expected is None:
            return False

        # For strings, do case-insensitive substring search
        if isinstance(actual, str) and isinstance(expected, str):
            return expected.lower() in actual.lower()

        # For lists/arrays, check membership
        if isinstance(actual, (list, tuple)):
            return expected in actual

        # For other types, convert to string and search
        try:
            return str(expected).lower() in str(actual).lower()
        except:
            return False

    def _compare_numeric_values(self, actual: Any, expected: Any, operator: str) -> bool:
        """Compare two values numerically."""
        try:
            # Try to convert both to float for comparison
            actual_num = float(actual)
            expected_num = float(expected)

            if operator == "lt":
                return actual_num < expected_num
            elif operator == "gt":
                return actual_num > expected_num
            elif operator == "lte":
                return actual_num <= expected_num
            elif operator == "gte":
                return actual_num >= expected_num
            else:
                raise ValueError(f"Unsupported numeric operator: {operator}")

        except (ValueError, TypeError):
            # If numeric conversion fails, fall back to string comparison
            try:
                actual_str = str(actual)
                expected_str = str(expected)

                if operator == "lt":
                    return actual_str < expected_str
                elif operator == "gt":
                    return actual_str > expected_str
                elif operator == "lte":
                    return actual_str <= expected_str
                elif operator == "gte":
                    return actual_str >= expected_str
                else:
                    return False
            except:
                return False

    def search_notes(
        self,
        spec: ExtractionSpec,
        search: str,
        search_target: Literal["text", "metadata", "id", "all"],
        patient_ids: Optional[List[str]] = None,
        full: bool = False,
        config_dir: Optional[str] = None
    ) -> List[Patient]:
        """
        Search notes by text, metadata, id, or all fields at the database level.

        Args:
            spec: ExtractionSpec containing the note queries
            search: Search term to look for
            search_target: What to search in - "text", "metadata", "id", or "all"
            patient_ids: Optional list of patient IDs to filter by first
            full: If False, return metadata only (like get_note_metadata).
                  If True, return full notes with text (like get_notes)
            config_dir: Directory containing the config file

        Returns:
            List of Patient objects matching the search criteria.
            Structure matches get_note_metadata when full=False, get_notes when full=True.
        """
        if not search or not search.strip():
            # If no search term, fall back to regular get methods
            if full:
                return self.get_notes(spec, patient_ids, config_dir)
            else:
                return self.get_note_metadata(spec, patient_ids, config_dir, counts_only=True)

        search_term = f"%{search.lower().strip()}%"

        # Get CTEs
        metadata_cte = self._load_metadata_cte(spec, config_dir)
        text_cte = self._load_text_cte(spec, config_dir)

        # Build search conditions
        search_conditions = []

        # Search in patient ID
        if search_target in ("all", "id"):
            search_conditions.append(
                sa.func.lower(metadata_cte.c.patient_id).like(search_term)
            )

        # Search in patient metadata
        if search_target in ("all", "metadata"):
            search_conditions.append(
                sa.func.lower(metadata_cte.c.patient_metadata).like(search_term)
            )

        # Search in note metadata
        if search_target in ("all", "metadata"):
            search_conditions.append(
                sa.func.lower(metadata_cte.c.note_metadata).like(search_term)
            )

        # Search in note text (only if we have text data)
        if search_target in ("all", "text"):
            if text_cte is not None:
                search_conditions.append(
                    sa.func.lower(text_cte.c.note_text).like(search_term)
                )
            elif hasattr(metadata_cte.c, 'note_text'):
                # Single query case - text is in metadata CTE
                search_conditions.append(
                    sa.func.lower(metadata_cte.c.note_text).like(search_term)
                )

        # Combine search conditions with OR
        if not search_conditions:
            raise ValueError(f"No searchable fields for target '{search_target}'")

        search_condition = sa.or_(*search_conditions)

        # Build the main query
        if full:
            # Return full notes with text
            if text_cte is not None:
                # Join metadata and text CTEs
                query = select(
                    metadata_cte.c.patient_id,
                    metadata_cte.c.note_id,
                    metadata_cte.c.patient_metadata,
                    metadata_cte.c.note_metadata,
                    metadata_cte.c.note_date,
                    text_cte.c.note_text,
                ).select_from(
                    metadata_cte.join(
                        text_cte,
                        sa.and_(
                            metadata_cte.c.patient_id == text_cte.c.patient_id,
                            metadata_cte.c.note_id == text_cte.c.note_id,
                        ),
                    )
                ).where(search_condition)
            else:
                # Single query already has text column
                query = select(
                    metadata_cte.c.patient_id,
                    metadata_cte.c.note_id,
                    metadata_cte.c.patient_metadata,
                    metadata_cte.c.note_metadata,
                    metadata_cte.c.note_date,
                    metadata_cte.c.note_text,
                ).where(search_condition)
        else:
            # Return counts only - need to aggregate
            if text_cte is not None and search_target in ("all", "text"):
                # Need to join with text CTE for text search, then aggregate
                joined_cte = metadata_cte.join(
                    text_cte,
                    sa.and_(
                        metadata_cte.c.patient_id == text_cte.c.patient_id,
                        metadata_cte.c.note_id == text_cte.c.note_id,
                    ),
                ).alias("joined_cte")

                query = select(
                    joined_cte.c.patient_id,
                    joined_cte.c.patient_metadata,
                    sa.func.count(distinct(joined_cte.c.note_id)).label("note_count"),
                    sa.func.max(distinct(joined_cte.c.note_date)).label("latest_note_date"),
                    sa.func.min(distinct(joined_cte.c.note_date)).label("earliest_note_date")
                ).where(search_condition).group_by(
                    joined_cte.c.patient_id,
                    joined_cte.c.patient_metadata
                )
            else:
                # Can work with just metadata CTE
                query = select(
                    metadata_cte.c.patient_id,
                    metadata_cte.c.patient_metadata,
                    sa.func.count(distinct(metadata_cte.c.note_id)).label("note_count"),
                    sa.func.max(distinct(metadata_cte.c.note_date)).label("latest_note_date"),
                    sa.func.min(distinct(metadata_cte.c.note_date)).label("earliest_note_date")
                ).where(search_condition).group_by(
                    metadata_cte.c.patient_id,
                    metadata_cte.c.patient_metadata
                )

        # Apply patient ID filter if provided
        if patient_ids:
            query = query.where(metadata_cte.c.patient_id.in_(patient_ids))

        # Execute query
        with self.engine.connect() as conn:
            result = conn.execute(query)
            notes = [dict(row._mapping) for row in result]

        # Format results
        if full:
            # Group by patient for full results
            patients_data: Dict[str, Dict[str, Any]] = {}
            for row in notes:
                if not row.get("note_id"):
                    continue
                patient_id = row["patient_id"]
                if patient_id not in patients_data:
                    patients_data[patient_id] = Patient.from_database_value(dict(
                        id=patient_id,
                        metadata=row["patient_metadata"],
                        notes=[],
                        note_count=0,
                        earliest_note_date=None,
                        latest_note_date=None
                    ))

                # Create note with full data
                note = Note.from_database_value(dict(
                    id=row["note_id"],
                    note_text=row.get("note_text"),
                    date=row.get("note_date"),
                    metadata=row.get("note_metadata")
                ))
                pt = patients_data[patient_id]
                pt["notes"].append(note)
                pt["note_count"] += 1
                pt["earliest_note_date"] = note["date"] if pt["earliest_note_date"] is None else min(pt["earliest_note_date"], note["date"])
                pt["latest_note_date"] = note["date"] if pt["latest_note_date"] is None else max(pt["latest_note_date"], note["date"])

            return list(patients_data.values())
        else:
            # Return counts format
            return [
                {
                    "id": row["patient_id"],
                    "metadata": safe_load_json(row["patient_metadata"]),
                    "note_count": row["note_count"],
                    "earliest_note_date": row["earliest_note_date"],
                    "latest_note_date": row["latest_note_date"]
                }
                for row in notes
            ]


class EditableSourceDatabase(SourceDatabase):
    """
    Extends SourceDatabase with methods to insert and delete patients and notes.
    Assumes database contains:
    - 'patients' table with columns: id, metadata
    - 'notes' table with columns: id, metadata, note_text
    """

    def __init__(self, connection_string: Optional[str] = None, **connection_params):
        """Initialize EditableSourceDatabase with the same parameters as SourceDatabase."""
        super().__init__(connection_string, **connection_params)

        # Define table schemas
        self.metadata = MetaData()

        self.patients_table = Table(
            'patients', self.metadata,
            Column('id', String, primary_key=True),
            Column('metadata', String),
            autoload_with=self.engine
        )

        self.notes_table = Table(
            'notes', self.metadata,
            Column('id', String, primary_key=True),
            Column('patient_id', String),
            Column('metadata', String),
            Column('note_text', String),
            Column('date', String, nullable=True),
            autoload_with=self.engine
        )

    def insert_patients(self, patients: List[Patient], overwrite: bool = False) -> None:
        """
        Insert a list of Patient objects into the database.

        Args:
            patients: List of Patient objects to insert
            overwrite: If True, remove existing objects with the same IDs

        Raises:
            ValueError: If patient data is invalid
            Exception: If database insertion fails
        """
        if not patients:
            return

        with self.engine.begin() as conn:
            # Prepare patient data for insertion
            patient_records = []
            note_records = []

            for patient in patients:
                # Validate required fields
                if not patient.get('id'):
                    raise ValueError("Patient must have an 'id' field")

                # Prepare patient record
                patient_record = {
                    'id': patient['id'],
                    'metadata': patient.get('metadata', {})
                }
                patient_records.append(Patient.to_database_value(patient_record))

                # Prepare note records
                notes = patient.get('notes', [])
                for note in notes:
                    if not note.get('id'):
                        raise ValueError(f"Note for patient {patient['id']} must have an 'id' field")

                    note_record = {
                        'id': note['id'],
                        'patient_id': patient['id'],  # Foreign key to patient
                        'metadata': note.get('metadata', {}),
                        'note_text': note.get('note_text', ''),
                        'date': note.get('date')
                    }
                    note_records.append(Note.to_database_value(note_record))

            # Delete the patients if they already exist
            if overwrite:
                patient_ids = [patient['id'] for patient in patient_records]
                stmt = delete(self.notes_table).where(
                    self.notes_table.c.patient_id.in_(patient_ids)
                )
                conn.execute(stmt)
                stmt = delete(self.patients_table).where(
                    self.patients_table.c.id.in_(patient_ids)
                )
                conn.execute(stmt)

            # Insert patients first (due to foreign key constraints)
            if patient_records:
                stmt = insert(self.patients_table).values(patient_records)
                conn.execute(stmt)

            # Insert notes
            if note_records:
                stmt = insert(self.notes_table).values(note_records)
                conn.execute(stmt)

    def delete_patients(self, patient_ids: List[str]) -> None:
        """
        Delete patients and their associated notes by patient IDs.

        Args:
            patient_ids: List of patient IDs to delete

        Raises:
            Exception: If database deletion fails
        """
        if not patient_ids:
            return

        with self.engine.begin() as conn:
            # Delete notes first (due to foreign key constraints)
            stmt = delete(self.notes_table).where(
                self.notes_table.c.patient_id.in_(patient_ids)
            )
            conn.execute(stmt)

            # Delete patients
            stmt = delete(self.patients_table).where(
                self.patients_table.c.id.in_(patient_ids)
            )
            conn.execute(stmt)