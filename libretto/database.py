import json
import os
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Boolean, Text,
    ForeignKey, CheckConstraint, UniqueConstraint, select, insert, update,
    delete, and_, or_, func, text
)
from sqlalchemy.engine import Engine
from sqlalchemy.sql import Select
from .types import NoteExtraction, ExtractionResult, ExtractionSpec, Project, ExtractionTask, PatientComment, SpecComment, Patient, Note
from .filter_types import ExtractionFilter
import uuid

class LLMExtractDatabase:
    """Database interface for LLM extraction data using SQLAlchemy."""

    # Database versioning
    CURRENT_DB_VERSION = 12

    def __init__(self, connection_string: str, enable_wal: bool = False):
        """Initialize database connection and create schema if needed."""
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)

        # Set up metadata and table definitions
        self.metadata = MetaData()
        self._define_tables()

        # Check if database needs initialization
        if self._needs_initialization():
            print("Creating database schema")
            self.create()
        else:
            self.update()

        if enable_wal and connection_string.startswith('sqlite'):
            self._enable_wal_mode()

    def _define_tables(self):
        """Define SQLAlchemy table objects."""
        self.specs_table = Table(
            'specs', self.metadata,
            Column('id', String, primary_key=True),
            Column('name', String),
            Column('executor', String, default='noteextract'),
            Column('content', Text),
            Column('date_added', String),
            Column('date_modified', String),
            Column('spec_version', Integer, default=1),
            Column('is_current', Boolean, default=True),
            Column('parent_version_id', String, nullable=True),
            Column('project_id', Integer, ForeignKey('projects.id'), nullable=True),
            Column('deleted', Boolean, default=False)
        )

        self.extractions_table = Table(
            'extractions', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('patient_id', String, nullable=False),
            Column('spec_id', String),
            Column('extraction_class', String),
            Column('annotator_id', Integer, ForeignKey('users.id'), nullable=True),
            Column('project_id', Integer, ForeignKey('projects.id'), nullable=True)
        )

        self.extraction_attributes_table = Table(
            'extraction_attributes', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('extraction_id', Integer, ForeignKey('extractions.id'), nullable=False),
            Column('name', String, nullable=False),
            Column('value', Text)
        )

        self.extraction_citations_table = Table(
            'extraction_citations', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('extraction_id', Integer, ForeignKey('extractions.id'), nullable=False),
            Column('note_id', String),
            Column('quote', Text),
            Column('start_pos', Integer),
            Column('end_pos', Integer)
        )

        self.extraction_tasks_table = Table(
            'extraction_tasks', self.metadata,
            Column('id', String, primary_key=True),
            Column('spec_id', String, ForeignKey('specs.id'), nullable=False),
            Column('patient_ids', Text),
            Column('status', String, nullable=False),
            Column('status_message', Text),
            Column('created_at', String, nullable=False),
            Column('started_at', String),
            Column('completed_at', String),
            Column('error_message', Text),
            Column('progress_current', Integer, default=0),
            Column('progress_total', Integer, default=0),
            Column('project_id', Integer, ForeignKey('projects.id'), nullable=True)
        )

        self.feedback_table = Table(
            'feedback', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('annotator_id', Integer, ForeignKey('users.id'), nullable=True),
            Column('extraction_id', Integer, ForeignKey('extractions.id')),
            Column('approved', Boolean),
            Column('rejected', Boolean),
            Column('comment', Text),
            Column('created_at', String, nullable=False),
            Column('updated_at', String, nullable=False),
            Column('is_current', Boolean, default=True),
            Column('parent_version_id', Integer, nullable=True),
            Column('deleted', Boolean, default=False)
        )

        self.prompt_history_table = Table(
            'prompt_history', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('date_added', String, nullable=False),
            Column('type', String, nullable=False),
            Column('spec_id', String, ForeignKey('specs.id')),
            Column('prompt', Text, nullable=False),
            Column('response', Text, nullable=False),
        )

        self.tags_table = Table(
            'tags', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('patient_id', String, nullable=False),
            Column('tag', String, nullable=False),
            Column('created_at', String, nullable=False),
            Column('project_id', Integer, ForeignKey('projects.id'), nullable=True),
            UniqueConstraint('patient_id', 'tag', 'project_id')
        )

        self.users_table = Table(
            'users', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('username', String, unique=True, nullable=False),
            Column('password_hash', String, nullable=False),
            Column('created_at', String, nullable=False),
            Column('last_login', String, nullable=True),
            Column('is_admin', Boolean, nullable=True, default=False),
        )

        self.projects_table = Table(
            'projects', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('name', String, nullable=False),
            Column('source_connection', String, nullable=False),
            Column('source_read_only', Boolean, nullable=False, default=False),
            Column('note_metadata_query', Text, nullable=True),
            Column('note_text_query', Text, nullable=True),
            Column('environment_vars', Text, nullable=True),
            Column('created_at', String, nullable=False),
            Column('updated_at', String, nullable=False)
        )

        self.user_projects_table = Table(
            'user_projects', self.metadata,
            Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
            Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
            Column('created_at', String, nullable=False)
        )

        self.patient_comments_table = Table(
            'patient_comments', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('patient_id', String, nullable=False),
            Column('annotator_id', Integer, ForeignKey('users.id'), nullable=False),
            Column('comment', Text, nullable=False),
            Column('created_at', String, nullable=False),
            Column('updated_at', String, nullable=False),
            Column('project_id', Integer, ForeignKey('projects.id'), nullable=True),
            Column('is_current', Boolean, default=True),
            Column('parent_version_id', Integer, nullable=True),
            Column('deleted', Boolean, default=False)
        )

        self.spec_comments_table = Table(
            'spec_comments', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('spec_id', String, nullable=False),
            Column('annotator_id', Integer, ForeignKey('users.id'), nullable=False),
            Column('comment', Text, nullable=False),
            Column('created_at', String, nullable=False),
            Column('updated_at', String, nullable=False),
            Column('project_id', Integer, ForeignKey('projects.id'), nullable=True),
            Column('is_current', Boolean, default=True),
            Column('parent_version_id', Integer, nullable=True),
            Column('deleted', Boolean, default=False)
        )

    def _needs_initialization(self) -> bool:
        """Check if database needs to be initialized."""
        try:
            with self.engine.connect() as conn:
                # Check if specs table exists
                return not conn.dialect.has_table(conn, 'specs')
        except Exception:
            return True

    def create(self) -> None:
        """Initialize the database with the required schema."""
        # Create all tables
        self.metadata.create_all(self.engine)

        # Set the database version to the current version for new databases
        self.set_database_version(self.CURRENT_DB_VERSION)

    def _enable_wal_mode(self) -> None:
        """Enable WAL mode for concurrent access (SQLite only)."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))  # 30 second timeout
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()

    def get_database_version(self) -> int:
        with self.engine.connect() as conn:
            result = conn.execute(text("PRAGMA user_version"))
            return result.fetchone()[0]

    def set_database_version(self, version: int) -> None:
        with self.engine.connect() as conn:
            conn.execute(text(f"PRAGMA user_version = {version}"))
            conn.commit()

    def update(self) -> None:
        """Update database schema to the latest version using incremental migrations."""
        current_version = self.get_database_version()
        target_version = self.CURRENT_DB_VERSION

        if current_version == target_version:
            return
        if current_version > target_version:
            print(f"Warning: Database version {current_version} is newer than expected {target_version}")
            return

        print(f"Updating database from version {current_version} to {target_version}")

        # Apply migrations incrementally
        for version in range(current_version + 1, target_version + 1):
            print(f"Applying migration to version {version}")

            self.migrate(version)
            self.set_database_version(version)

        print(f"Database update complete. Now at version {target_version}")

    def insert_extractions(
        self,
        patient_id: str,
        spec_id: str,
        extractions: List[NoteExtraction],
        overwrite: bool = True,
        project_id: Optional[int] = None
    ) -> None:
        """
        Add extractions to the database.
        """
        if overwrite:
            # Delete existing extractions for the patient/spec (cascade via subquery)
            with self.engine.connect() as conn:
                extraction_ids_subq = select(self.extractions_table.c.id).where(
                    and_(
                        self.extractions_table.c.patient_id == patient_id,
                        self.extractions_table.c.spec_id == spec_id
                    )
                )
                conn.execute(delete(self.extraction_attributes_table).where(
                    self.extraction_attributes_table.c.extraction_id.in_(extraction_ids_subq)
                ))
                conn.execute(delete(self.extraction_citations_table).where(
                    self.extraction_citations_table.c.extraction_id.in_(extraction_ids_subq)
                ))
                conn.execute(delete(self.extractions_table).where(
                    and_(
                        self.extractions_table.c.patient_id == patient_id,
                        self.extractions_table.c.spec_id == spec_id
                    )
                ))
                conn.commit()

        if not extractions:
            return

        with self.engine.connect() as conn:
            for extraction in extractions:
                # Insert into extractions table
                result = conn.execute(
                    insert(self.extractions_table).values(
                        patient_id=patient_id,
                        spec_id=spec_id,
                        extraction_class=extraction.get('extraction_class'),
                        annotator_id=None,
                        project_id=project_id
                    )
                )
                extraction_id = result.inserted_primary_key[0]

                # Insert attributes
                attrs = extraction.get('attributes') or {}
                if isinstance(attrs, str):
                    try:
                        attrs = json.loads(attrs)
                    except (json.JSONDecodeError, TypeError):
                        attrs = {}
                for name, value in attrs.items():
                    conn.execute(insert(self.extraction_attributes_table).values(
                        extraction_id=extraction_id,
                        name=name,
                        value=str(value) if value is not None else None
                    ))

                citations = extraction.get('citations', [])
                if citations:
                    conn.execute(
                        insert(self.extraction_citations_table),
                        [{
                            "extraction_id": extraction_id,
                            "note_id": citation["note_id"],
                            "quote": citation["quote"],
                            "start_pos": citation["char_interval"].get("start_pos") if citation.get("char_interval") else None,
                            "end_pos": citation["char_interval"].get("end_pos") if citation.get("char_interval") else None,
                        } for citation in citations]
                    )

            conn.commit()

    def insert_extraction_result(
        self,
        extraction_result: ExtractionResult,
        spec_id: str,
        overwrite: bool = True,
        project_id: Optional[int] = None
    ) -> None:
        """Insert an ExtractionResult object into the database.

        This method handles unified extractions and responses (responses have char_interval=None).

        Args:
            extraction_result: The ExtractionResult object containing all extractions and responses
            spec_id: The ID of the extraction specification used to generate these results
            overwrite: Whether to overwrite existing data with the same keys
        """
        patient_id = extraction_result['patient_id']

        if extractions := extraction_result.get('extractions'):
            # Group extractions by whether they're patient-level or note-level
            note_level_extractions = []
            patient_level_extractions = []

            for extraction in extractions:
                # Determine level based on note_id presence
                if extraction['note_id'] is None:
                    patient_level_extractions.append(extraction)
                else:
                    note_level_extractions.append(extraction)

            # Insert note-level extractions
            if note_level_extractions:
                self.insert_extractions(
                    patient_id=patient_id,
                    spec_id=spec_id,
                    extractions=note_level_extractions,
                    overwrite=overwrite,
                    project_id=project_id
                )

            # Insert patient-level extractions
            if patient_level_extractions:
                self.insert_extractions(
                    patient_id=patient_id,
                    spec_id=spec_id,
                    extractions=patient_level_extractions,
                    overwrite=overwrite,
                    project_id=project_id
                )

    # Task management methods
    def create_extraction_task(
        self,
        task_id: str,
        spec_id: str,
        patient_ids: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> None:
        """Create a new extraction task record."""
        task = ExtractionTask(
            id=task_id,
            spec_id=spec_id,
            patient_ids=patient_ids,
            status='pending',
            created_at=datetime.now(timezone.utc).isoformat(),
            project_id=project_id
        )
        with self.engine.connect() as conn:
            insert_stmt = insert(self.extraction_tasks_table).values(
                **ExtractionTask.to_database_value(task)
            )
            conn.execute(insert_stmt)
            conn.commit()

    def update_task_status(
        self,
        task_id: str,
        status: str,
        status_message: Optional[str] = None,
        error_message: Optional[str] = None,
        progress_current: Optional[int] = None,
        progress_total: Optional[int] = None
    ) -> None:
        """Update task status and progress."""
        # Build update values dynamically
        update_values = {'status': status}

        if status == 'running' and progress_current is not None:
            update_values['started_at'] = datetime.now(timezone.utc).isoformat()
        elif status in ('completed', 'failed', 'canceled'):
            update_values['completed_at'] = datetime.now(timezone.utc).isoformat()

        if error_message is not None:
            update_values['error_message'] = error_message

        if progress_current is not None:
            update_values['progress_current'] = progress_current

        if progress_total is not None:
            update_values['progress_total'] = progress_total

        if status_message is not None:
            update_values['status_message'] = status_message

        with self.engine.connect() as conn:
            update_stmt = update(self.extraction_tasks_table).where(
                self.extraction_tasks_table.c.id == task_id
            ).values(**update_values)
            conn.execute(update_stmt)
            conn.commit()

    def get_task_status(self, task_id: str) -> Optional[ExtractionTask]:
        """Get current task status and details."""
        with self.engine.connect() as conn:
            select_stmt = select(
                self.extraction_tasks_table.c.id,
                self.extraction_tasks_table.c.spec_id,
                self.extraction_tasks_table.c.patient_ids,
                self.extraction_tasks_table.c.status,
                self.extraction_tasks_table.c.status_message,
                self.extraction_tasks_table.c.created_at,
                self.extraction_tasks_table.c.started_at,
                self.extraction_tasks_table.c.completed_at,
                self.extraction_tasks_table.c.error_message,
                self.extraction_tasks_table.c.progress_current,
                self.extraction_tasks_table.c.progress_total
            ).where(self.extraction_tasks_table.c.id == task_id)

            result = conn.execute(select_stmt)
            row = result.fetchone()
            if row is None:
                return None

            return ExtractionTask.from_database_value(dict(row._mapping))

    def cancel_task(self, task_id: str) -> bool:
        """Mark task as canceled."""
        with self.engine.connect() as conn:
            update_stmt = update(self.extraction_tasks_table).where(
                and_(
                    self.extraction_tasks_table.c.id == task_id,
                    self.extraction_tasks_table.c.status.in_(['pending', 'running'])
                )
            ).values(
                status='canceled',
                completed_at=datetime.now(timezone.utc).isoformat()
            )
            result = conn.execute(update_stmt)
            conn.commit()
            return result.rowcount > 0

    def _database_rows_to_patients(self, rows: list) -> list[Patient]:
        """
        Converts a list of rows returned from the database to a set of patients. There should
        be one row per note, and the rows should be dictionaries with the following keys:
        id, patient_id, metadata, note_text, patient_metadata
        """
        patients = {}
        for row in rows:
            if row["patient_id"] not in patients:
                patients[row["patient_id"]] = Patient(id=row["patient_id"], metadata=json.loads(row.get("patient_metadata") or '{}'), notes=[])

            metadata = json.loads(row.get("metadata") or {})
            patients[row["patient_id"]]["notes"].append(Note(
                id=row["id"],
                note_text=row["note_text"],
                metadata=metadata
            ))

        return list(patients.values())

    def insert_feedback(self, feedback_data: Dict[str, Any], project_id: Optional[int] = None) -> int:
        """Insert or update feedback for extraction or response with versioning."""
        if "extraction_id" not in feedback_data:
            raise ValueError("extraction_id field is required for feedback")

        # Check if this is a deletion request (approved=False, rejected=False, no comment)
        approved = feedback_data.get('approved', False)
        rejected = feedback_data.get('rejected', False)
        comment = feedback_data.get('comment', '')

        if not approved and not rejected and not comment:
            # This is a deletion request
            deleted = self.delete_feedback(feedback_data["extraction_id"], project_id)
            return -1 if deleted else 0  # Return -1 to indicate deletion

        # Validate project access if project_id is provided
        if project_id is not None:
            extraction_project_id = self.get_extraction_project_id(feedback_data["extraction_id"])
            self.validate_project_access(extraction_project_id, project_id)

        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            # Check for existing current feedback
            select_stmt = select(
                self.feedback_table.c.id,
                self.feedback_table.c.approved,
                self.feedback_table.c.rejected,
                self.feedback_table.c.comment
            ).where(
                and_(
                    self.feedback_table.c.extraction_id == feedback_data['extraction_id'],
                    self.feedback_table.c.is_current == True,
                    self.feedback_table.c.deleted == False
                )
            )

            result = conn.execute(select_stmt)
            existing = result.fetchone()

            if existing:
                # Check if content has changed
                content_changed = (
                    existing.approved != feedback_data.get('approved') or
                    existing.rejected != feedback_data.get('rejected') or
                    existing.comment != feedback_data.get('comment')
                )

                if content_changed:
                    # Create new version - mark old as non-current
                    update_old_stmt = update(self.feedback_table).where(
                        self.feedback_table.c.id == existing.id
                    ).values(is_current=False)
                    conn.execute(update_old_stmt)

                    # Insert new version
                    insert_stmt = insert(self.feedback_table).values(
                        annotator_id=feedback_data.get('annotator_id'),
                        extraction_id=feedback_data.get('extraction_id'),
                        approved=feedback_data.get('approved'),
                        rejected=feedback_data.get('rejected'),
                        comment=feedback_data.get('comment'),
                        created_at=current_time,
                        updated_at=current_time,
                        is_current=True,
                        parent_version_id=existing.id
                    )
                    result = conn.execute(insert_stmt)
                    conn.commit()
                    return result.lastrowid
                else:
                    # No content change, just update timestamp
                    update_stmt = update(self.feedback_table).where(
                        self.feedback_table.c.id == existing.id
                    ).values(updated_at=current_time)
                    conn.execute(update_stmt)
                    conn.commit()
                    return existing.id
            else:
                # Insert new feedback (first version)
                insert_stmt = insert(self.feedback_table).values(
                    annotator_id=feedback_data.get('annotator_id'),
                    extraction_id=feedback_data.get('extraction_id'),
                    approved=feedback_data.get('approved'),
                    rejected=feedback_data.get('rejected'),
                    comment=feedback_data.get('comment'),
                    created_at=current_time,
                    updated_at=current_time,
                    is_current=True,
                    parent_version_id=None
                )
                result = conn.execute(insert_stmt)
                conn.commit()
                return result.lastrowid

    def delete_feedback(self, extraction_id: int, project_id: Optional[int] = None) -> bool:
        """Soft delete feedback for an extraction and all its prior versions. Returns True if deleted."""
        # Validate project access if project_id is provided
        if project_id is not None:
            extraction_project_id = self.get_extraction_project_id(extraction_id)
            self.validate_project_access(extraction_project_id, project_id)

        with self.engine.connect() as conn:
            # Find current feedback
            current_stmt = select(self.feedback_table.c.id).where(
                and_(
                    self.feedback_table.c.extraction_id == extraction_id,
                    self.feedback_table.c.is_current == True,
                    self.feedback_table.c.deleted == False
                )
            )
            result = conn.execute(current_stmt)
            current_row = result.fetchone()

            if not current_row:
                return False

            # Traverse version chain and delete all versions
            current_id = current_row[0]
            deleted_count = 0

            while current_id is not None:
                stmt = select(
                    self.feedback_table.c.parent_version_id
                ).where(and_(
                    self.feedback_table.c.id == current_id
                ))

                result = conn.execute(stmt).fetchone()
                if result:
                    # Soft delete this feedback
                    update_stmt = update(self.feedback_table).where(
                        self.feedback_table.c.id == current_id
                    ).values(deleted=True, is_current=False)
                    conn.execute(update_stmt)
                    deleted_count += 1
                    current_id = result[0]  # Move to parent version
                else:
                    break

            conn.commit()
            return deleted_count > 0

    def get_specs(self, note_id: Optional[str] = None, current_only: bool = False, project_id: Optional[int] = None) -> List[ExtractionSpec]:
        """Get specs, optionally filtered by note_id. Returns all versions by default unless current_only=True."""
        with self.engine.connect() as conn:
            if note_id is not None:
                query = select(self.specs_table).select_from(
                    self.specs_table.join(
                        self.extractions_table,
                        self.specs_table.c.id == self.extractions_table.c.spec_id
                    ).join(
                        self.extraction_citations_table,
                        self.extractions_table.c.id == self.extraction_citations_table.c.extraction_id
                    )
                ).where(
                    self.extraction_citations_table.c.note_id == note_id
                ).distinct()

                # Add current_only filter if requested
                if current_only:
                    query = query.where(self.specs_table.c.is_current == True)

                # Add project_id filter if requested
                if project_id is not None:
                    query = query.where(self.specs_table.c.project_id == project_id)

                # Filter out deleted specs
                query = query.where(self.specs_table.c.deleted == False)

                query = query.order_by(
                    self.specs_table.c.date_modified.desc()
                )
            else:
                query = select(self.specs_table)

                # Add current_only filter if requested
                if current_only:
                    query = query.where(self.specs_table.c.is_current == True)

                # Add project_id filter if requested
                if project_id is not None:
                    query = query.where(self.specs_table.c.project_id == project_id)

                # Filter out deleted specs
                query = query.where(self.specs_table.c.deleted == False)

                query = query.order_by(
                    self.specs_table.c.date_modified.desc()
                )

            result = conn.execute(query)
            specs = [ExtractionSpec.from_database_value(dict(row._mapping))
                     for row in result]

            return specs

    def get_spec_by_id(self, spec_id: str, version: Optional[int] = None, current_only: bool = False) -> Optional[ExtractionSpec]:
        """Get a spec by ID. If version is specified, gets that version. If current_only=True (default), gets current version."""
        with self.engine.connect() as conn:
            query = select(self.specs_table).where(and_(
                self.specs_table.c.id == spec_id,
                self.specs_table.c.deleted == False
            ))

            if version is not None:
                query = query.where(self.specs_table.c.spec_version == version)
            elif current_only:
                query = query.where(self.specs_table.c.is_current == True)
            else:
                # If neither version nor current_only, get the latest version
                query = query.order_by(self.specs_table.c.spec_version.desc()).limit(1)

            result = conn.execute(query)
            row = result.fetchone()
            if row is None:
                return None

            spec = ExtractionSpec.from_database_value(dict(row._mapping))
            return spec

    def update_spec_by_id(self, spec_id: str, new_spec: ExtractionSpec, project_id: Optional[int] = None, force_overwrite: bool = False) -> str:
        """
        Update or insert a spec by ID with automatic versioning. If force_overwrite is True,
        always rewrites the existing spec if it exists; otherwise, creates a new version.
        """
        # Validate project access if project_id is provided and spec exists
        if project_id is not None:
            existing_spec = self.get_spec_by_id(spec_id, current_only=True)
            if existing_spec:
                existing_project_id = existing_spec.get('project_id')
                self.validate_project_access(existing_project_id, project_id)

        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        new_spec = ExtractionSpec.to_database_value(new_spec)
        print("new spec:", new_spec)

        with self.engine.connect() as conn:
            # Check if spec exists and get current version
            existing_stmt = select(
                self.specs_table.c.id,
                self.specs_table.c.spec_version,
                self.specs_table.c.executor,
                self.specs_table.c.content,
                self.specs_table.c.is_current,
            ).where(
                and_(
                    self.specs_table.c.id == spec_id,
                    self.specs_table.c.deleted == False
                )
            )
            existing = conn.execute(existing_stmt).fetchone()

            if existing and not existing[-1] and not force_overwrite:
                # Updating an old version of the spec - need to create
                # a new root version
                spec_id = str(uuid.uuid4())
                new_spec = {**new_spec, "name": "Fork of " + new_spec.get("name", "")}
                existing = None

            if existing:
                # Check if content has changed (compare executor and content fields)
                needs_new_version = (
                    existing.executor != new_spec.get('executor') or
                    existing.content != new_spec.get('content')
                ) and not force_overwrite

                if needs_new_version:
                    # Create new version
                    current_version = existing.spec_version
                    new_version = current_version + 1

                    # Mark old version as non-current
                    update_old_stmt = update(self.specs_table).where(
                        and_(
                            self.specs_table.c.id == spec_id,
                            self.specs_table.c.spec_version == current_version
                        )
                    ).values(is_current=False)
                    conn.execute(update_old_stmt)

                    # Insert new version
                    new_id = uuid.uuid4().hex
                    insert_new_stmt = insert(self.specs_table).values(
                        id=new_id,
                        name=new_spec.get('name'),
                        executor=new_spec.get('executor', 'noteextract'),
                        content=new_spec.get('content'),
                        spec_version=new_version,
                        is_current=True,
                        parent_version_id=spec_id,
                        date_added=current_time,
                        date_modified=current_time,
                        project_id=project_id
                    )
                    conn.execute(insert_new_stmt)
                    conn.commit()
                    return new_id
                else:
                    update_stmt = update(self.specs_table).where(
                        and_(
                            self.specs_table.c.id == spec_id,
                            self.specs_table.c.is_current == True,
                            self.specs_table.c.deleted == False
                        )
                    ).values(
                        name=new_spec.get('name'),
                        date_modified=current_time,
                        executor=new_spec.get('executor', 'noteextract'),
                        content=new_spec.get('content')
                    )
                    conn.execute(update_stmt)
                    conn.commit()
                    return spec_id
            else:
                # Insert new spec (first version)
                insert_stmt = insert(self.specs_table).values(
                    id=spec_id,
                    name=new_spec.get('name'),
                    executor=new_spec.get('executor', 'noteextract'),
                    content=new_spec.get('content'),
                    spec_version=1,
                    is_current=True,
                    parent_version_id=None,
                    date_added=current_time,
                    date_modified=current_time,
                    project_id=project_id
                )
                conn.execute(insert_stmt)
                conn.commit()
                return spec_id

    def delete_spec_by_id(self, spec_id: str, project_id: Optional[int] = None) -> None:
        """Soft delete a spec by ID, including all its prior versions."""
        # Validate project access if project_id is provided
        if project_id is not None:
            spec_project_id = self.get_spec_project_id(spec_id)
            self.validate_project_access(spec_project_id, project_id)

        with self.engine.connect() as conn:
            current_id = spec_id
            while current_id is not None:
                specs = self.specs_table
                stmt = select(
                    specs.c.parent_version_id
                ).where(and_(
                    specs.c.id == current_id,
                    specs.c.deleted == False
                ))
                result = conn.execute(stmt).fetchone()
                if result:
                    # soft delete this spec and move on to its parent
                    update_stmt = update(self.specs_table).where(
                        self.specs_table.c.id == current_id
                    ).values(deleted=True)
                    conn.execute(update_stmt)
                    conn.commit()
                    current_id = result[0]
                else:
                    break

    def list_extraction_tasks(self, project_id: Optional[str] = None) -> List[ExtractionTask]:
        """List all extraction tasks."""
        with self.engine.connect() as conn:
            # Create aliases for tables
            et = self.extraction_tasks_table
            specs = self.specs_table

            # Build the query with JOIN
            stmt = select(
                et,
                specs.c.name.label('spec_name')
            ).select_from(
                et.outerjoin(specs, et.c.spec_id == specs.c.id)
            )
            if project_id != None:
                stmt = stmt.where(et.c.project_id == project_id)
            stmt = stmt.order_by(et.c.created_at.desc())

            result = conn.execute(stmt)
            return [ExtractionTask.from_database_value(dict(row._mapping)) for row in result.fetchall()]

    def find_running_extraction_task(self, filters: Dict[str, Optional[str]]) -> Optional[ExtractionTask]:
        """Find running extraction task matching filters."""
        where_conditions = []

        if filters.get('specID'):
            where_conditions.append(self.extraction_tasks_table.c.spec_id == filters['specID'])
        if filters.get('patientID'):
            where_conditions.append(self.extraction_tasks_table.c.patient_ids.like(f'%"{filters["patientID"]}"%'))

        if not where_conditions:
            return None

        with self.engine.connect() as conn:
            # Create aliases for tables
            et = self.extraction_tasks_table
            specs = self.specs_table

            # Build the query with JOIN and WHERE conditions
            stmt = select(
                et,
                specs.c.name.label('spec_name')
            ).select_from(
                et.outerjoin(specs, et.c.spec_id == specs.c.id)
            ).where(
                and_(*where_conditions)
            ).order_by(et.c.created_at.desc()).limit(1)

            result = conn.execute(stmt)
            row = result.fetchone()

            if row is None:
                return None

            return ExtractionTask.from_database_value(dict(row._mapping))

    def get_extraction_task(self, task_id: str) -> Optional[ExtractionTask]:
        """Get extraction task by ID."""
        with self.engine.connect() as conn:
            # Create aliases for tables
            et = self.extraction_tasks_table
            specs = self.specs_table

            # Build the query with JOIN
            stmt = select(
                et,
                specs.c.name.label('spec_name')
            ).select_from(
                et.outerjoin(specs, et.c.spec_id == specs.c.id)
            ).where(et.c.id == task_id)

            result = conn.execute(stmt)
            row = result.fetchone()

            if row is None:
                return None

            return ExtractionTask.from_database_value(dict(row._mapping))

    def list_completed_extraction_patients(self, project_id: str, spec_id: Optional[str]) -> set[str]:
        """List patients that have at least one completed extraction task for the given spec."""
        with self.engine.connect() as conn:
            # Create aliases for tables
            et = self.extraction_tasks_table

            where_clauses = [
                et.c.project_id == project_id,
                et.c.status == 'completed'
            ]
            if spec_id:
                where_clauses.append(et.c.spec_id == spec_id)

            stmt = select(
                et.c.patient_ids
            ).where(
                and_(*where_clauses)
            ).order_by(et.c.created_at.desc()).limit(1)

            result = conn.execute(stmt)

            patient_ids = set()
            for row in result.fetchall():
                try:
                    ids = json.loads(row[0])
                    patient_ids |= set(ids)
                except json.JSONDecodeError:
                    continue

            return patient_ids
        
    def get_existing_results(self, extraction_source: Optional[ExtractionSpec], patient_id: Optional[str], project_id: Optional[int] = None) -> ExtractionResult:
        """Get existing extraction results. All extractions and responses unified."""
        where_conditions = []

        if patient_id:
            where_conditions.append(self.extractions_table.c.patient_id == patient_id)

        if extraction_source:
            where_conditions.append(self.extractions_table.c.spec_id == extraction_source['id'])

        if project_id is not None:
            where_conditions.append(self.extractions_table.c.project_id == project_id)

        with self.engine.connect() as conn:
            # Fetch extractions with feedback join
            stmt = select(
                self.extractions_table,
                self.feedback_table.c.id.label('feedback_id'),
                self.feedback_table.c.approved,
                self.feedback_table.c.rejected,
                self.feedback_table.c.comment,
                self.feedback_table.c.created_at.label('feedback_created_at'),
                self.feedback_table.c.updated_at.label('feedback_updated_at')
            ).select_from(
                self.extractions_table.outerjoin(
                    self.feedback_table,
                    and_(self.extractions_table.c.id == self.feedback_table.c.extraction_id,
                         self.feedback_table.c.is_current == True,
                         self.feedback_table.c.deleted == False))
            )

            if where_conditions:
                stmt = stmt.where(and_(*where_conditions))

            result = conn.execute(stmt)
            extraction_rows = [dict(row._mapping) for row in result.fetchall()]

            if not extraction_rows:
                extracted_patients = self.list_completed_extraction_patients(project_id, extraction_source["id"] if extraction_source is not None else None)
                if patient_id is None:
                    return {}
                return {
                    'patient_id': patient_id,
                    'extraction_run': patient_id in extracted_patients,
                    'extractions': []
                }

            extraction_ids = [row['id'] for row in extraction_rows]

            # Fetch citations for all extraction IDs
            cit_stmt = select(self.extraction_citations_table).where(
                self.extraction_citations_table.c.extraction_id.in_(extraction_ids)
            )
            cit_result = conn.execute(cit_stmt)
            citations_by_id: Dict[int, list] = {}
            for cit_row in cit_result.fetchall():
                cit = dict(cit_row._mapping)
                eid = cit['extraction_id']
                has_char_interval = cit['start_pos'] is not None and cit['end_pos'] is not None
                citations_by_id.setdefault(eid, []).append({
                    'note_id': cit['note_id'],
                    'quote': cit['quote'],
                    'char_interval': {
                        'start_pos': cit['start_pos'],
                        'end_pos': cit['end_pos']
                    } if has_char_interval else None
                })

            # Fetch attributes for all extraction IDs
            attr_stmt = select(self.extraction_attributes_table).where(
                self.extraction_attributes_table.c.extraction_id.in_(extraction_ids)
            )
            attr_result = conn.execute(attr_stmt)
            attributes_by_id: Dict[int, dict] = {}
            for attr_row in attr_result.fetchall():
                attr = dict(attr_row._mapping)
                eid = attr['extraction_id']
                value = attr['value']
                if attr['name'] in ('conflict_flag', 'uncertainty_flag'):
                    try:
                        value = value.lower() in ('true', 'yes', '1')
                    except:
                        pass
                attributes_by_id.setdefault(eid, {})[attr['name']] = value

        extracted_patients = self.list_completed_extraction_patients(project_id, extraction_source["id"] if extraction_source is not None else None)

        # Group results by patient_id
        results_by_patient = {}

        for row in extraction_rows:
            patient_id_key = row['patient_id']
            if patient_id_key not in results_by_patient:
                results_by_patient[patient_id_key] = {
                    'patient_id': patient_id_key,
                    'extraction_run': patient_id_key in extracted_patients,
                    'extractions': []
                }

            feedback = {
                'id': row['feedback_id'],
                'approved': row['approved'],
                'rejected': row['rejected'],
                'comment': row['comment'],
                'created_at': row['feedback_created_at'],
                'updated_at': row['feedback_updated_at']
            } if row['feedback_id'] is not None else None

            extraction_id = row['id']
            extraction = {
                'id': extraction_id,
                'spec_id': row['spec_id'],
                'extraction_class': row['extraction_class'],
                'attributes': attributes_by_id.get(extraction_id) or None,
                'citations': citations_by_id.get(extraction_id, []),
                'feedback': feedback
            }

            results_by_patient[patient_id_key]['extractions'].append(extraction)

        if patient_id is None:
            return results_by_patient

        if not results_by_patient:
            return {
                'patient_id': patient_id,
                'extraction_run': patient_id in extracted_patients,
                'extractions': []
            }

        return list(results_by_patient.values())[0]

    def clear_existing_results(self, extraction_source: Optional[ExtractionSpec], patient_ids: Optional[List[str]], project_id: Optional[int] = None):
        """Remove extractions and responses corresponding to the given patient ID and/or spec."""
        where_conditions = []

        if patient_ids:
            where_conditions.append(self.extractions_table.c.patient_id.in_(patient_ids))

        if extraction_source:
            where_conditions.append(self.extractions_table.c.spec_id == extraction_source['id'])

        if project_id is not None:
            where_conditions.append(self.extractions_table.c.project_id == project_id)

        with self.engine.connect() as conn:
            # Build subquery for matching extraction IDs
            extraction_ids_subq = select(self.extractions_table.c.id)
            if where_conditions:
                extraction_ids_subq = extraction_ids_subq.where(and_(*where_conditions))

            # Delete from sub-tables first, then extractions
            conn.execute(delete(self.extraction_attributes_table).where(
                self.extraction_attributes_table.c.extraction_id.in_(extraction_ids_subq)
            ))
            conn.execute(delete(self.extraction_citations_table).where(
                self.extraction_citations_table.c.extraction_id.in_(extraction_ids_subq)
            ))

            delete_stmt = delete(self.extractions_table)
            if where_conditions:
                delete_stmt = delete_stmt.where(and_(*where_conditions))
            conn.execute(delete_stmt)
            conn.commit()

    def get_patients_count(self) -> int:
        """Get count of distinct patients in extractions."""
        with self.engine.connect() as conn:
            stmt = select(func.count(self.extractions_table.c.patient_id.distinct()))
            result = conn.execute(stmt)
            return result.fetchone()[0]

    def get_patients_with_extractions(self, spec_id: Optional[str] = None, project_id: Optional[int] = None) -> List[str]:
        """Return a list of patient IDs that have extractions (optionally for a specific extraction spec)."""
        with self.engine.connect() as conn:
            stmt = select(self.extractions_table.c.patient_id.distinct())

            where_conditions = []
            if spec_id:
                where_conditions.append(self.extractions_table.c.spec_id == spec_id)
            if project_id is not None:
                where_conditions.append(self.extractions_table.c.project_id == project_id)

            if where_conditions:
                stmt = stmt.where(and_(*where_conditions))

            result = conn.execute(stmt)
            return [row[0] for row in result.fetchall()]

    def add_prompt_history(
        self,
        type_str: str,
        prompt: str,
        response: Optional[str] = None,
        spec_id: Optional[str] = None
    ) -> int:
        """Add a new prompt history entry."""
        from datetime import datetime

        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            insert_stmt = insert(self.prompt_history_table).values(
                date_added=current_time,
                type=type_str,
                spec_id=spec_id,
                prompt=prompt,
                response=response or ''
            )
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def list_prompt_history(
        self,
        type_filter: Optional[str] = None,
        spec_id_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List prompt history entries, optionally filtered by type and/or spec_id."""
        where_conditions = []

        if type_filter:
            where_conditions.append(self.prompt_history_table.c.type == type_filter)

        if spec_id_filter:
            where_conditions.append(self.prompt_history_table.c.spec_id == spec_id_filter)

        with self.engine.connect() as conn:
            stmt = select(
                func.max(self.prompt_history_table.c.date_added).label("date_added"),
                func.max(self.prompt_history_table.c.type).label("type"),
                func.max(self.prompt_history_table.c.spec_id).label("spec_id"),
                self.prompt_history_table.c.prompt
            ).group_by(self.prompt_history_table.c.prompt).order_by(self.prompt_history_table.c.date_added.desc())

            if where_conditions:
                stmt = stmt.where(and_(*where_conditions))

            if limit:
                stmt = stmt.limit(limit)

            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result.fetchall()]

    # Tag management methods
    def add_tag_to_patients(self, patient_ids: List[str], tag: str, project_id: Optional[int] = None) -> None:
        """Add a tag to a list of patient IDs."""
        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            # For each patient ID, try to insert the tag (ignore if it already exists)
            for patient_id in patient_ids:
                try:
                    insert_stmt = insert(self.tags_table).values(
                        patient_id=patient_id,
                        tag=tag,
                        created_at=current_time,
                        project_id=project_id
                    )
                    conn.execute(insert_stmt)
                except Exception:
                    # Ignore duplicate key errors (tag already exists for this patient)
                    pass
            conn.commit()

    def remove_tag_from_patients(self, patient_ids: List[str], tag: str, project_id: Optional[int] = None) -> None:
        """Remove a tag from a list of patient IDs."""
        if not patient_ids:
            return

        with self.engine.connect() as conn:
            where_conditions = [
                self.tags_table.c.patient_id.in_(patient_ids),
                self.tags_table.c.tag == tag
            ]
            if project_id is not None:
                where_conditions.append(self.tags_table.c.project_id == project_id)

            delete_stmt = delete(self.tags_table).where(and_(*where_conditions))
            conn.execute(delete_stmt)
            conn.commit()

    def get_tags_for_patients(self, patient_ids: List[str], project_id: Optional[int] = None) -> Dict[str, List[str]]:
        """Get all tags for a list of patient IDs. Returns dict mapping patient_id -> list of tags."""
        if not patient_ids:
            return {}

        with self.engine.connect() as conn:
            where_conditions = [self.tags_table.c.patient_id.in_(patient_ids)]
            if project_id is not None:
                where_conditions.append(self.tags_table.c.project_id == project_id)

            stmt = select(
                self.tags_table.c.patient_id,
                self.tags_table.c.tag
            ).where(
                and_(*where_conditions)
            ).order_by(
                self.tags_table.c.patient_id,
                self.tags_table.c.tag
            )

            result = conn.execute(stmt)

            tags_dict = {}
            for row in result.fetchall():
                patient_id, tag = row
                tags_dict.setdefault(patient_id, []).append(tag)

            return tags_dict

    def get_patients_with_tag(self, tag: str, project_id: Optional[int] = None) -> List[str]:
        """Get all patient IDs that have a specific tag."""
        with self.engine.connect() as conn:
            where_conditions = [self.tags_table.c.tag == tag]
            if project_id is not None:
                where_conditions.append(self.tags_table.c.project_id == project_id)

            stmt = select(
                self.tags_table.c.patient_id.distinct()
            ).where(
                and_(*where_conditions)
            ).order_by(
                self.tags_table.c.patient_id
            )

            result = conn.execute(stmt)
            return [row[0] for row in result.fetchall()]

    def get_extraction_counts(self, spec_id: str) -> Dict[str, int]:
        """Get the count of extractions per patient for a given spec ID.

        Returns a dictionary mapping patient_id -> extraction_count.
        """
        with self.engine.connect() as conn:
            stmt = select(
                self.extractions_table.c.patient_id,
                func.count(self.extractions_table.c.id).label('extraction_count')
            ).where(
                self.extractions_table.c.spec_id == spec_id
            ).group_by(
                self.extractions_table.c.patient_id
            )

            result = conn.execute(stmt)
            return {row.patient_id: row.extraction_count for row in result.fetchall()}

    def get_patients_with_extraction_filters(self, filters: List[ExtractionFilter], project_id: Optional[int] = None) -> List[str]:
        """
        Filter patients by extraction classes and attribute values using application-level filtering.

        Args:
            filters: List of ExtractionFilter dicts
            project_id: Project ID to filter by

        Returns:
            List of patient IDs that match all extraction filters (AND logic)
        """
        if not filters:
            return []

        # Get all extractions for the relevant specs and project
        spec_ids = list(set(f["spec_id"] for f in filters))

        with self.engine.connect() as conn:
            where_conditions = []

            # Filter by spec IDs
            if spec_ids:
                where_conditions.append(self.extractions_table.c.spec_id.in_(spec_ids))

            # Filter by project
            if project_id is not None:
                where_conditions.append(self.extractions_table.c.project_id == project_id)

            stmt = select(
                self.extractions_table.c.id,
                self.extractions_table.c.patient_id,
                self.extractions_table.c.spec_id,
                self.extractions_table.c.extraction_class,
            )

            if where_conditions:
                stmt = stmt.where(and_(*where_conditions))

            result = conn.execute(stmt)
            extraction_rows = [dict(row._mapping) for row in result.fetchall()]

            # Fetch attributes for these extractions
            ext_ids = [r['id'] for r in extraction_rows]
            attributes_by_id: Dict[int, dict] = {}
            if ext_ids:
                attr_stmt = select(self.extraction_attributes_table).where(
                    self.extraction_attributes_table.c.extraction_id.in_(ext_ids)
                )
                for attr_row in conn.execute(attr_stmt).fetchall():
                    attr = dict(attr_row._mapping)
                    attributes_by_id.setdefault(attr['extraction_id'], {})[attr['name']] = attr['value']

            extractions = [
                {**r, 'attributes': attributes_by_id.get(r['id'], {})}
                for r in extraction_rows
            ]

        # Apply filters to each extraction and collect matching patient IDs
        matching_patient_ids = set()

        # Group extractions by patient ID for efficient processing
        extractions_by_patient = {}
        for extraction in extractions:
            patient_id = extraction["patient_id"]
            if patient_id not in extractions_by_patient:
                extractions_by_patient[patient_id] = []
            extractions_by_patient[patient_id].append(extraction)

        # Check each patient against all filters
        for patient_id, patient_extractions in extractions_by_patient.items():
            if self._evaluate_extraction_filters(patient_extractions, filters):
                matching_patient_ids.add(patient_id)

        return list(matching_patient_ids)

    def _evaluate_extraction_filters(self, extractions: List[Dict], filters: List[ExtractionFilter]) -> bool:
        """
        Evaluate whether patient's extractions match all filters (AND logic).

        Args:
            extractions: List of extraction dicts for a single patient
            filters: List of ExtractionFilter dicts

        Returns:
            True if all filters match, False otherwise
        """
        for filter_spec in filters:
            if not self._evaluate_single_extraction_filter(extractions, filter_spec):
                return False
        return True

    def _evaluate_single_extraction_filter(self, extractions: List[Dict], filter_spec: ExtractionFilter) -> bool:
        """
        Evaluate a single extraction filter against patient's extractions.

        Args:
            extractions: List of extraction dicts for a single patient
            filter_spec: Single ExtractionFilter dict

        Returns:
            True if filter matches, False otherwise
        """
        spec_id = filter_spec["spec_id"]
        extraction_class = filter_spec["extraction_class"]
        operator = filter_spec["operator"]
        attribute_name = filter_spec.get("attribute")
        expected_value = filter_spec.get("value")

        # Filter extractions to only those matching spec and class
        relevant_extractions = [
            ext for ext in extractions
            if ext["spec_id"] == spec_id and ext["extraction_class"] == extraction_class
        ]

        # For "exists" operator, just check if any extractions exist
        if operator == "exists":
            return len(relevant_extractions) > 0

        # For other operators, need to check attribute values
        if not attribute_name:
            raise ValueError(f"Attribute name required for operator: {operator}")

        # Check if any extraction has the matching attribute value
        for extraction in relevant_extractions:
            attributes = extraction.get("attributes") or {}

            if attribute_name in attributes:
                actual_value = attributes[attribute_name]
                if self._compare_extraction_value(actual_value, expected_value, operator):
                    return True

        return False

    def _compare_extraction_value(self, actual: Any, expected: Any, operator: str) -> bool:
        """Compare extraction attribute values using the specified operator."""
        if operator == "eq":
            return self._values_equal(actual, expected)
        elif operator == "contains":
            return self._value_contains(actual, expected)
        elif operator in ["lt", "gt", "lte", "gte"]:
            return self._compare_numeric_values(actual, expected, operator)
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def _values_equal(self, actual: Any, expected: Any) -> bool:
        """Compare two values for equality, handling type coercion."""
        if actual is None or expected is None:
            return actual == expected

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

    def get_available_extraction_classes_and_attributes(self, project_id: Optional[int] = None) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        """
        Discover available extraction classes and attributes by spec.

        Args:
            project_id: Project ID to filter by

        Returns:
            Dict with structure: {spec_id: {spec_name: str, classes: {class_name: {attributes: [attr_names]}}}}
        """
        with self.engine.connect() as conn:
            # Get specs and their names
            spec_where_conditions = [self.specs_table.c.is_current == True, self.specs_table.c.deleted == False]
            if project_id is not None:
                spec_where_conditions.append(self.specs_table.c.project_id == project_id)

            spec_stmt = select(
                self.specs_table.c.id,
                self.specs_table.c.name
            ).where(and_(*spec_where_conditions))

            spec_result = conn.execute(spec_stmt)
            specs = {row.id: row.name for row in spec_result.fetchall()}

            if not specs:
                return {}

            # Get extractions for these specs joined with their attributes
            extract_where_conditions = [self.extractions_table.c.spec_id.in_(list(specs.keys()))]
            if project_id is not None:
                extract_where_conditions.append(self.extractions_table.c.project_id == project_id)

            extract_stmt = select(
                self.extractions_table.c.id,
                self.extractions_table.c.spec_id,
                self.extractions_table.c.extraction_class,
            ).where(and_(*extract_where_conditions))

            extract_result = conn.execute(extract_stmt)
            extraction_rows = [dict(row._mapping) for row in extract_result.fetchall()]

            # Fetch attribute names for these extractions
            ext_ids = [r['id'] for r in extraction_rows]
            attr_names_by_id: Dict[int, list] = {}
            if ext_ids:
                attr_stmt = select(
                    self.extraction_attributes_table.c.extraction_id,
                    self.extraction_attributes_table.c.name
                ).where(self.extraction_attributes_table.c.extraction_id.in_(ext_ids))
                for attr_row in conn.execute(attr_stmt).fetchall():
                    attr_names_by_id.setdefault(attr_row[0], []).append(attr_row[1])

        # Build the structure
        result = {}

        for extraction in extraction_rows:
            spec_id = extraction["spec_id"]
            extraction_class = extraction["extraction_class"]

            if spec_id not in result:
                result[spec_id] = {
                    "name": specs.get(spec_id, spec_id),
                    "classes": {}
                }

            if extraction_class not in result[spec_id]["classes"]:
                result[spec_id]["classes"][extraction_class] = {"attributes": set()}

            for attr_name in attr_names_by_id.get(extraction["id"], []):
                result[spec_id]["classes"][extraction_class]["attributes"].add(attr_name)

        # Convert sets to sorted lists
        for spec_id in result:
            for class_name in result[spec_id]["classes"]:
                result[spec_id]["classes"][class_name]["attributes"] = sorted(
                    list(result[spec_id]["classes"][class_name]["attributes"])
                )

        return result

    # User management methods
    def create_user(self, username: str, password_hash: str, is_admin: bool = False) -> int:
        """Create a new user. Returns user ID."""
        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            insert_stmt = insert(self.users_table).values(
                username=username,
                password_hash=password_hash,
                created_at=current_time,
                is_admin=is_admin
            )
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        with self.engine.connect() as conn:
            stmt = select(self.users_table).where(self.users_table.c.username == username)
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return dict(row._mapping)

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        with self.engine.connect() as conn:
            stmt = select(self.users_table).where(self.users_table.c.id == user_id)
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return dict(row._mapping)

    def update_user_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            update_stmt = update(self.users_table).where(
                self.users_table.c.id == user_id
            ).values(last_login=current_time)
            conn.execute(update_stmt)
            conn.commit()

    def update_user_password(self, user_id: int, password_hash: str) -> None:
        """Update user's password hash."""
        with self.engine.connect() as conn:
            update_stmt = update(self.users_table).where(
                self.users_table.c.id == user_id
            ).values(password_hash=password_hash)
            conn.execute(update_stmt)
            conn.commit()

    def update_user_privileges(self, user_id: int, is_admin: bool = False) -> None:
        """Update user's admin privileges."""
        with self.engine.connect() as conn:
            update_stmt = update(self.users_table).where(
                self.users_table.c.id == user_id
            ).values(is_admin=is_admin)
            conn.execute(update_stmt)
            conn.commit()

    def delete_user(self, user_id: int) -> bool:
        """Delete user by ID. Returns True if user was deleted."""
        with self.engine.connect() as conn:
            delete_stmt = delete(self.users_table).where(self.users_table.c.id == user_id)
            result = conn.execute(delete_stmt)
            conn.commit()
            return result.rowcount > 0

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users (without password hashes)."""
        with self.engine.connect() as conn:
            stmt = select(
                self.users_table.c.id,
                self.users_table.c.username,
                self.users_table.c.created_at,
                self.users_table.c.last_login,
                self.users_table.c.is_admin
            ).order_by(self.users_table.c.username)
            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result.fetchall()]

    # Project management methods
    def create_project(self, project: Project) -> int:
        """Create a new project. Returns project ID."""
        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        project = {**Project.to_database_value(project),
                   "created_at": current_time,
                   "updated_at": current_time}

        with self.engine.connect() as conn:
            insert_stmt = insert(self.projects_table).values(**project)
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """Get project by ID."""
        with self.engine.connect() as conn:
            stmt = select(self.projects_table).where(self.projects_table.c.id == project_id)
            result = conn.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return Project.from_database_value(dict(row._mapping))

    def update_project(self, project_id: int, project: Project) -> bool:
        """Update project. Returns True if project was updated."""
        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        update_values = {**Project.to_database_value(project), 
                         'updated_at': current_time}

        with self.engine.connect() as conn:
            update_stmt = update(self.projects_table).where(
                self.projects_table.c.id == project_id
            ).values(**update_values)
            result = conn.execute(update_stmt)
            conn.commit()
            return result.rowcount > 0

    def delete_project(self, project_id: int) -> bool:
        """Delete project by ID. Returns True if project was deleted."""
        with self.engine.connect() as conn:
            delete_stmt = delete(self.projects_table).where(self.projects_table.c.id == project_id)
            result = conn.execute(delete_stmt)
            conn.commit()
            return result.rowcount > 0

    def list_projects(self, user_id: Optional[int] = None) -> List[Project]:
        """List all projects, optionally filtered by user membership."""
        with self.engine.connect() as conn:
            if user_id is not None:
                stmt = select(self.projects_table).select_from(
                    self.projects_table.join(
                        self.user_projects_table,
                        self.projects_table.c.id == self.user_projects_table.c.project_id
                    )
                ).where(
                    self.user_projects_table.c.user_id == user_id
                ).order_by(self.projects_table.c.name)
            else:
                stmt = select(self.projects_table).order_by(self.projects_table.c.name)
            result = conn.execute(stmt)
            return [Project.from_database_value(dict(row._mapping)) for row in result.fetchall()]

    # User-project membership methods
    def add_user_to_project(self, user_id: int, project_id: int) -> bool:
        """Add a user to a project. Returns True if added, False if already exists."""
        from datetime import datetime
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            try:
                insert_stmt = insert(self.user_projects_table).values(
                    user_id=user_id,
                    project_id=project_id,
                    created_at=current_time
                )
                conn.execute(insert_stmt)
                conn.commit()
                return True
            except Exception:
                return False

    def remove_user_from_project(self, user_id: int, project_id: int) -> bool:
        """Remove a user from a project. Returns True if removed."""
        with self.engine.connect() as conn:
            delete_stmt = delete(self.user_projects_table).where(
                and_(
                    self.user_projects_table.c.user_id == user_id,
                    self.user_projects_table.c.project_id == project_id
                )
            )
            result = conn.execute(delete_stmt)
            conn.commit()
            return result.rowcount > 0

    def get_users_in_project(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all users in a project."""
        with self.engine.connect() as conn:
            stmt = select(
                self.users_table.c.id,
                self.users_table.c.username,
                self.users_table.c.created_at,
                self.users_table.c.last_login,
                self.user_projects_table.c.created_at.label('added_at')
            ).select_from(
                self.users_table.join(
                    self.user_projects_table,
                    self.users_table.c.id == self.user_projects_table.c.user_id
                )
            ).where(
                self.user_projects_table.c.project_id == project_id
            ).order_by(self.users_table.c.username)
            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result.fetchall()]

    def get_user_projects(self, user_id: int) -> List[Project]:
        """Get all projects for a user."""
        with self.engine.connect() as conn:
            stmt = select(
                self.projects_table,
                self.user_projects_table.c.created_at.label('added_at')
            ).select_from(
                self.projects_table.join(
                    self.user_projects_table,
                    self.projects_table.c.id == self.user_projects_table.c.project_id
                )
            ).where(
                self.user_projects_table.c.user_id == user_id
            ).order_by(self.projects_table.c.name)
            result = conn.execute(stmt)
            return [Project.from_database_value(dict(row._mapping)) for row in result.fetchall()]

    def user_has_project_access(self, user_id: int, project_id: int) -> bool:
        """Check if a user has access to a project."""
        with self.engine.connect() as conn:
            stmt = select(self.user_projects_table.c.user_id).where(
                and_(
                    self.user_projects_table.c.user_id == user_id,
                    self.user_projects_table.c.project_id == project_id
                )
            )
            result = conn.execute(stmt)
            return result.fetchone() is not None

    def validate_project_access(self, resource_project_id: Optional[int], user_project_id: Optional[int]) -> None:
        """Validate that project IDs match for update operations. Raises ValueError if they don't match."""
        if resource_project_id is not None and user_project_id is not None:
            if resource_project_id != user_project_id:
                raise ValueError(f"Project ID mismatch: resource belongs to project {resource_project_id}, but operation requested for project {user_project_id}")
        elif resource_project_id is not None and user_project_id is None:
            raise ValueError(f"Resource belongs to project {resource_project_id}, but no project specified in operation")
        elif resource_project_id is None and user_project_id is not None:
            raise ValueError(f"Resource has no project, but operation requested for project {user_project_id}")

    def get_extraction_project_id(self, extraction_id: int) -> Optional[int]:
        """Get the project ID for an extraction."""
        with self.engine.connect() as conn:
            stmt = select(self.extractions_table.c.project_id).where(
                self.extractions_table.c.id == extraction_id
            )
            result = conn.execute(stmt)
            row = result.fetchone()
            return row[0] if row else None

    def get_spec_project_id(self, spec_id: str) -> Optional[int]:
        """Get the project ID for a spec."""
        with self.engine.connect() as conn:
            stmt = select(self.specs_table.c.project_id).where(
                self.specs_table.c.id == spec_id
            )
            result = conn.execute(stmt)
            row = result.fetchone()
            return row[0] if row else None

    # Comment management methods
    def create_patient_comment(self, patient_id: str, annotator_id: int, comment: str, project_id: Optional[int] = None) -> int:
        """Create a new patient comment. Returns comment ID."""
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            insert_stmt = insert(self.patient_comments_table).values(
                patient_id=patient_id,
                annotator_id=annotator_id,
                comment=comment,
                created_at=current_time,
                updated_at=current_time,
                project_id=project_id
            )
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def create_spec_comment(self, spec_id: str, annotator_id: int, comment: str, project_id: Optional[int] = None) -> int:
        """Create a new spec comment. Returns comment ID."""
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            insert_stmt = insert(self.spec_comments_table).values(
                spec_id=spec_id,
                annotator_id=annotator_id,
                comment=comment,
                created_at=current_time,
                updated_at=current_time,
                project_id=project_id
            )
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def get_patient_comments(self, patient_id: str, current_only: bool = True, project_id: Optional[int] = None) -> List[PatientComment]:
        """Get comments for a patient. Returns current versions by default unless current_only=False."""
        with self.engine.connect() as conn:
            stmt = select(
                self.patient_comments_table.c.id,
                self.patient_comments_table.c.patient_id,
                self.patient_comments_table.c.annotator_id,
                self.patient_comments_table.c.comment,
                self.patient_comments_table.c.created_at,
                self.patient_comments_table.c.updated_at,
                self.users_table.c.username
            ).select_from(
                self.patient_comments_table.join(
                    self.users_table,
                    self.patient_comments_table.c.annotator_id == self.users_table.c.id,
                    isouter=True
                )
            ).where(and_(
                self.patient_comments_table.c.patient_id == patient_id,
                self.patient_comments_table.c.deleted == False
            )).order_by(self.patient_comments_table.c.created_at.desc())

            # Add current_only filter if requested
            if current_only:
                stmt = stmt.where(self.patient_comments_table.c.is_current == True)

            if project_id is not None:
                stmt = stmt.where(self.patient_comments_table.c.project_id == project_id)

            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result.fetchall()]

    def get_spec_comments(self, spec_id: str, current_only: bool = True, project_id: Optional[int] = None) -> List[SpecComment]:
        """Get comments for a spec. Returns current versions by default unless current_only=False."""
        with self.engine.connect() as conn:
            stmt = select(
                self.spec_comments_table.c.id,
                self.spec_comments_table.c.spec_id,
                self.spec_comments_table.c.annotator_id,
                self.spec_comments_table.c.comment,
                self.spec_comments_table.c.created_at,
                self.spec_comments_table.c.updated_at,
                self.users_table.c.username
            ).select_from(
                self.spec_comments_table.join(
                    self.users_table,
                    self.spec_comments_table.c.annotator_id == self.users_table.c.id,
                    isouter=True
                )
            ).where(and_(
                self.spec_comments_table.c.spec_id == spec_id,
                self.spec_comments_table.c.deleted == False
            )).order_by(self.spec_comments_table.c.created_at.desc())

            # Add current_only filter if requested
            if current_only:
                stmt = stmt.where(self.spec_comments_table.c.is_current == True)

            if project_id is not None:
                stmt = stmt.where(self.spec_comments_table.c.project_id == project_id)

            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result.fetchall()]

    def update_patient_comment(self, comment_id: int, comment: str, annotator_id: int) -> int:
        """Update a patient comment with versioning. Returns new comment ID."""
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            # Get existing comment
            select_stmt = select(
                self.patient_comments_table.c.id,
                self.patient_comments_table.c.patient_id,
                self.patient_comments_table.c.comment,
                self.patient_comments_table.c.project_id
            ).where(
                and_(
                    self.patient_comments_table.c.id == comment_id,
                    self.patient_comments_table.c.annotator_id == annotator_id,
                    self.patient_comments_table.c.is_current == True,
                    self.patient_comments_table.c.deleted == False
                )
            )

            result = conn.execute(select_stmt)
            existing = result.fetchone()

            if not existing:
                return 0

            # Check if content changed
            if existing.comment == comment:
                # No change, just update timestamp
                update_stmt = update(self.patient_comments_table).where(
                    self.patient_comments_table.c.id == comment_id
                ).values(updated_at=current_time)
                conn.execute(update_stmt)
                conn.commit()
                return comment_id

            # Create new version
            # Mark old as non-current
            update_old_stmt = update(self.patient_comments_table).where(
                self.patient_comments_table.c.id == comment_id
            ).values(is_current=False)
            conn.execute(update_old_stmt)

            # Insert new version
            insert_stmt = insert(self.patient_comments_table).values(
                patient_id=existing.patient_id,
                annotator_id=annotator_id,
                comment=comment,
                created_at=current_time,
                updated_at=current_time,
                project_id=existing.project_id,
                is_current=True,
                parent_version_id=comment_id
            )
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def update_spec_comment(self, comment_id: int, comment: str, annotator_id: int) -> int:
        """Update a spec comment with versioning. Returns new comment ID."""
        current_time = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            # Get existing comment
            select_stmt = select(
                self.spec_comments_table.c.id,
                self.spec_comments_table.c.spec_id,
                self.spec_comments_table.c.comment,
                self.spec_comments_table.c.project_id
            ).where(
                and_(
                    self.spec_comments_table.c.id == comment_id,
                    self.spec_comments_table.c.annotator_id == annotator_id,
                    self.spec_comments_table.c.is_current == True,
                    self.spec_comments_table.c.deleted == False
                )
            )

            result = conn.execute(select_stmt)
            existing = result.fetchone()

            if not existing:
                return 0

            # Check if content changed
            if existing.comment == comment:
                # No change, just update timestamp
                update_stmt = update(self.spec_comments_table).where(
                    self.spec_comments_table.c.id == comment_id
                ).values(updated_at=current_time)
                conn.execute(update_stmt)
                conn.commit()
                return comment_id

            # Create new version
            # Mark old as non-current
            update_old_stmt = update(self.spec_comments_table).where(
                self.spec_comments_table.c.id == comment_id
            ).values(is_current=False)
            conn.execute(update_old_stmt)

            # Insert new version
            insert_stmt = insert(self.spec_comments_table).values(
                spec_id=existing.spec_id,
                annotator_id=annotator_id,
                comment=comment,
                created_at=current_time,
                updated_at=current_time,
                project_id=existing.project_id,
                is_current=True,
                parent_version_id=comment_id
            )
            result = conn.execute(insert_stmt)
            conn.commit()
            return result.lastrowid

    def delete_patient_comment(self, comment_id: int, annotator_id: int) -> bool:
        """Soft delete a patient comment and all its prior versions. Returns True if deleted."""
        with self.engine.connect() as conn:
            # Traverse version chain and delete all versions
            current_id = comment_id
            deleted_count = 0

            while current_id is not None:
                # Check if current comment exists and belongs to annotator
                stmt = select(
                    self.patient_comments_table.c.parent_version_id
                ).where(and_(
                    self.patient_comments_table.c.id == current_id,
                    self.patient_comments_table.c.annotator_id == annotator_id,
                    self.patient_comments_table.c.deleted == False
                ))

                result = conn.execute(stmt).fetchone()
                if result:
                    # Soft delete this comment
                    update_stmt = update(self.patient_comments_table).where(
                        self.patient_comments_table.c.id == current_id
                    ).values(deleted=True)
                    conn.execute(update_stmt)
                    deleted_count += 1
                    current_id = result[0]  # Move to parent version
                else:
                    break

            conn.commit()
            return deleted_count > 0

    def delete_spec_comment(self, comment_id: int, annotator_id: int) -> bool:
        """Soft delete a spec comment and all its prior versions. Returns True if deleted."""
        with self.engine.connect() as conn:
            # Traverse version chain and delete all versions
            current_id = comment_id
            deleted_count = 0

            while current_id is not None:
                # Check if current comment exists and belongs to annotator
                stmt = select(
                    self.spec_comments_table.c.parent_version_id
                ).where(and_(
                    self.spec_comments_table.c.id == current_id,
                    self.spec_comments_table.c.annotator_id == annotator_id,
                    self.spec_comments_table.c.deleted == False
                ))

                result = conn.execute(stmt).fetchone()
                if result:
                    # Soft delete this comment
                    update_stmt = update(self.spec_comments_table).where(
                        self.spec_comments_table.c.id == current_id
                    ).values(deleted=True)
                    conn.execute(update_stmt)
                    deleted_count += 1
                    current_id = result[0]  # Move to parent version
                else:
                    break

            conn.commit()
            return deleted_count > 0

    def get_patient_comment_by_id(self, comment_id: int) -> Optional[PatientComment]:
        """Get a patient comment by ID."""
        with self.engine.connect() as conn:
            stmt = select(
                self.patient_comments_table.c.id,
                self.patient_comments_table.c.patient_id,
                self.patient_comments_table.c.annotator_id,
                self.patient_comments_table.c.comment,
                self.patient_comments_table.c.created_at,
                self.patient_comments_table.c.updated_at,
                self.patient_comments_table.c.project_id,
                self.users_table.c.username
            ).select_from(
                self.patient_comments_table.join(
                    self.users_table,
                    self.patient_comments_table.c.annotator_id == self.users_table.c.id,
                    isouter=True
                )
            ).where(and_(
                self.patient_comments_table.c.id == comment_id,
                self.patient_comments_table.c.deleted == False
            ))
            result = conn.execute(stmt)
            row = result.fetchone()
            return dict(row._mapping) if row else None

    def get_spec_comment_by_id(self, comment_id: int) -> Optional[SpecComment]:
        """Get a spec comment by ID."""
        with self.engine.connect() as conn:
            stmt = select(
                self.spec_comments_table.c.id,
                self.spec_comments_table.c.spec_id,
                self.spec_comments_table.c.annotator_id,
                self.spec_comments_table.c.comment,
                self.spec_comments_table.c.created_at,
                self.spec_comments_table.c.updated_at,
                self.spec_comments_table.c.project_id,
                self.users_table.c.username
            ).select_from(
                self.spec_comments_table.join(
                    self.users_table,
                    self.spec_comments_table.c.annotator_id == self.users_table.c.id,
                    isouter=True
                )
            ).where(and_(
                self.spec_comments_table.c.id == comment_id,
                self.spec_comments_table.c.deleted == False
            ))
            result = conn.execute(stmt)
            row = result.fetchone()
            return dict(row._mapping) if row else None

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self, 'engine') and self.engine:
            self.engine.dispose()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    ### Migrations

    def migrate(self, target_version: int) -> None:
        """Migrates versions by one."""
        with self.engine.connect() as conn:
            if target_version == 1:
                # Check if the old column exists
                table_info = conn.execute(text("PRAGMA table_info(extraction_tasks)"))
                columns = {row[1] for row in table_info.fetchall()}

                if 'patient_id' in columns and 'patient_ids' not in columns:
                    conn.execute(text("ALTER TABLE extraction_tasks ADD COLUMN patient_ids TEXT"))
                    conn.execute(text("""
                        UPDATE extraction_tasks
                        SET patient_ids = CASE
                            WHEN patient_id IS NOT NULL THEN json_array(patient_id)
                            ELSE NULL
                        END
                    """))
                    conn.execute(text("UPDATE extraction_tasks SET patient_id = NULL"))
                    conn.commit()
            elif target_version == 2:
                # Add tags table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(patient_id, tag)
                    )
                """))
                conn.commit()
            elif target_version == 3:
                # response_id column is removed - just ignore it
                pass
            elif target_version == 4:
                # Add versioning columns to specs table
                conn.execute(text("ALTER TABLE specs ADD COLUMN spec_version INTEGER DEFAULT 1"))
                conn.execute(text("ALTER TABLE specs ADD COLUMN is_current BOOLEAN DEFAULT 1"))
                conn.execute(text("ALTER TABLE specs ADD COLUMN parent_version_id INTEGER NULL"))
                conn.commit()
            elif target_version == 5:
                # Add users table and update foreign key constraints
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_login TEXT NULL
                    )
                """))
                # Note: SQLite doesn't support adding foreign key constraints to existing tables
                # The foreign key constraints will be enforced by the ORM layer
                conn.commit()
            elif target_version == 6:
                from datetime import datetime
                current_time = datetime.now(timezone.utc).isoformat()

                # Add projects table and user_projects junction table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        source_connection TEXT NOT NULL,
                        source_read_only BOOLEAN NOT NULL,
                        note_metadata_query TEXT NULL,
                        note_text_query TEXT NULL,
                        environment_vars TEXT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_projects (
                        user_id INTEGER NOT NULL,
                        project_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (user_id, project_id),
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                """))

                # Create "Default Project"
                default_project_result = conn.execute(text("""
                    INSERT INTO projects (name, source_connection, source_read_only, created_at, updated_at)
                    VALUES ('Default Project', '', 0, :created_at, :updated_at)
                """), {"created_at": current_time, "updated_at": current_time})
                default_project_id = default_project_result.lastrowid

                # Add all existing users to the default project
                conn.execute(text("""
                    INSERT INTO user_projects (user_id, project_id, created_at)
                    SELECT id, :project_id, :created_at
                    FROM users
                """), {"project_id": default_project_id, "created_at": current_time})

                # Add project_id columns to existing tables
                try:
                    conn.execute(text("ALTER TABLE specs ADD COLUMN project_id INTEGER NULL"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE extractions ADD COLUMN project_id INTEGER NULL"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE extraction_tasks ADD COLUMN project_id INTEGER NULL"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE tags ADD COLUMN project_id INTEGER NULL"))
                except Exception:
                    pass

                # Update existing data to belong to the default project
                conn.execute(text("""
                    UPDATE specs SET project_id = :project_id WHERE project_id IS NULL
                """), {"project_id": default_project_id})

                conn.execute(text("""
                    UPDATE extractions SET project_id = :project_id WHERE project_id IS NULL
                """), {"project_id": default_project_id})

                conn.execute(text("""
                    UPDATE extraction_tasks SET project_id = :project_id WHERE project_id IS NULL
                """), {"project_id": default_project_id})

                conn.execute(text("""
                    UPDATE tags SET project_id = :project_id WHERE project_id IS NULL
                """), {"project_id": default_project_id})

                conn.commit()
            elif target_version == 7:
                # Add patient_comments and spec_comments tables
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS patient_comments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id TEXT NOT NULL,
                        annotator_id INTEGER NOT NULL,
                        comment TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        project_id INTEGER NULL,
                        FOREIGN KEY (annotator_id) REFERENCES users (id),
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS spec_comments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        spec_id TEXT NOT NULL,
                        annotator_id INTEGER NOT NULL,
                        comment TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        project_id INTEGER NULL,
                        FOREIGN KEY (annotator_id) REFERENCES users (id),
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )
                """))
                conn.commit()
            elif target_version == 8:
                # Add deleted columns to specs, patient_comments, and spec_comments tables
                try:
                    conn.execute(text("ALTER TABLE specs ADD COLUMN deleted BOOLEAN DEFAULT 0"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE patient_comments ADD COLUMN deleted BOOLEAN DEFAULT 0"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE spec_comments ADD COLUMN deleted BOOLEAN DEFAULT 0"))
                except Exception:
                    pass
                conn.commit()
            elif target_version == 9:
                # Add versioning columns to feedback, patient_comments, and spec_comments tables
                try:
                    conn.execute(text("ALTER TABLE feedback ADD COLUMN is_current BOOLEAN DEFAULT 1"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE feedback ADD COLUMN parent_version_id INTEGER NULL"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE feedback ADD COLUMN deleted BOOLEAN DEFAULT 0"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE patient_comments ADD COLUMN is_current BOOLEAN DEFAULT 1"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE patient_comments ADD COLUMN parent_version_id INTEGER NULL"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE spec_comments ADD COLUMN is_current BOOLEAN DEFAULT 1"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE spec_comments ADD COLUMN parent_version_id INTEGER NULL"))
                except Exception:
                    pass
                conn.commit()
            elif target_version == 10:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                except Exception:
                    pass
                conn.commit()
            elif target_version == 11:
                # Add executor and content columns; migrate existing spec data into content
                try:
                    conn.execute(text("ALTER TABLE specs ADD COLUMN executor TEXT DEFAULT 'noteextract'"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE specs ADD COLUMN content TEXT"))
                except Exception:
                    pass
                # Populate content from existing individual fields (old columns kept for safety)
                conn.execute(text("""
                    UPDATE specs SET content = json_object(
                        'prompt', prompt,
                        'schema', schema,
                        'examples', json(COALESCE(examples, 'null')),
                        'note_metadata_query', note_metadata_query,
                        'note_text_query', note_text_query,
                        'model_args', json(COALESCE(model_args, 'null'))
                    )
                """))
                conn.commit()
            elif target_version == 12:
                # Split extractions table into extractions, extraction_attributes, extraction_citations
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS extraction_attributes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        extraction_id INTEGER NOT NULL REFERENCES extractions(id),
                        name TEXT NOT NULL,
                        value TEXT
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS extraction_citations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        extraction_id INTEGER NOT NULL REFERENCES extractions(id),
                        note_id TEXT,
                        quote TEXT,
                        start_pos INTEGER,
                        end_pos INTEGER
                    )
                """))
                # Migrate attributes: parse JSON and insert one row per key
                attr_rows = conn.execute(text(
                    "SELECT id, attributes FROM extractions WHERE attributes IS NOT NULL AND attributes != '{}'"
                )).fetchall()
                attr_data = []
                for row in attr_rows:
                    try:
                        attrs = json.loads(row[1])
                        if isinstance(attrs, dict):
                            for name, value in attrs.items():
                                attr_data.append({
                                    'extraction_id': row[0],
                                    'name': name,
                                    'value': str(value) if value is not None else None
                                })
                    except (json.JSONDecodeError, AttributeError):
                        pass
                if attr_data:
                    conn.execute(
                        text("INSERT INTO extraction_attributes (extraction_id, name, value) VALUES (:extraction_id, :name, :value)"),
                        attr_data
                    )
                # Migrate citations: one row per extraction with note_id/text/positions
                cit_rows = conn.execute(text(
                    "SELECT id, note_id, extraction_text, start_pos, end_pos FROM extractions"
                )).fetchall()
                cit_data = [
                    {'extraction_id': r[0], 'note_id': r[1], 'quote': r[2], 'start_pos': r[3], 'end_pos': r[4]}
                    for r in cit_rows
                ]
                if cit_data:
                    conn.execute(
                        text("INSERT INTO extraction_citations (extraction_id, note_id, quote, start_pos, end_pos) VALUES (:extraction_id, :note_id, :quote, :start_pos, :end_pos)"),
                        cit_data
                    )
                # Recreate extractions table without old columns (SQLite doesn't support DROP COLUMN in older versions)
                conn.execute(text("""
                    CREATE TABLE extractions_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id TEXT NOT NULL,
                        spec_id TEXT,
                        extraction_class TEXT,
                        annotator_id INTEGER REFERENCES users(id),
                        project_id INTEGER REFERENCES projects(id)
                    )
                """))
                conn.execute(text(
                    "INSERT INTO extractions_new SELECT id, patient_id, spec_id, extraction_class, annotator_id, project_id FROM extractions"
                ))
                conn.execute(text("DROP TABLE extractions"))
                conn.execute(text("ALTER TABLE extractions_new RENAME TO extractions"))
                conn.commit()