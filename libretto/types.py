from typing import List, Any, Optional, Tuple, TypedDict, NotRequired
import json
import os
from contextlib import contextmanager
from collections.abc import Sequence
from .json_sanitize import safe_load_json

class Note(TypedDict):
    """A dictionary representing a patient note."""
    # The note ID
    id: str
    # The text of the note
    note_text: Optional[str]
    # Optional date field for the note
    date: NotRequired[Optional[str]]
    # Other information about the note, arbitrary schema but guaranteed JSON serializable
    metadata: dict[str, Any]

    @staticmethod
    def from_database_value(note: dict[str, Any]) -> "Note":
        note = {**note}
        if note.get('metadata'):
            note['metadata'] = safe_load_json(note['metadata'])
        return note
    
    @staticmethod
    def to_database_value(note: "Note") -> dict[str, Any]:
        note = {**note}
        if note.get('metadata') is not None:
            note['metadata'] = json.dumps(note['metadata'])
        return note

class Patient(TypedDict):
    # The patient ID
    id: str
    # Available notes for the patient
    notes: NotRequired[Sequence[Note]]
    # Count (if no actual note objects)
    note_count: int
    # Newest and oldest note date (if no actual note objects)
    earliest_note_date: Optional[str]
    latest_note_date: Optional[str]
    # Other information about the patient, arbitrary schema but guaranteed JSON serializable
    metadata: dict[str, Any]
    # Tags (if applicable)
    tags: NotRequired[List[str]]
    # Number of extractions for this patient (if applicable)
    extraction_count: NotRequired[int]
    # Whether or not the extraction model was run for this patient (if applicable)
    extraction_run: NotRequired[bool]

    @staticmethod
    def from_database_value(pt: dict[str, Any]) -> "Patient":
        pt = {**pt}
        if pt.get('metadata'):
            pt['metadata'] = safe_load_json(pt['metadata'])
        if pt.get('notes'):
            pt['notes'] = [Note.from_database_value(n) for n in pt['notes']]
        return pt
    
    @staticmethod
    def to_database_value(pt: "Patient") -> dict[str, Any]:
        pt = {**pt}
        if pt.get('metadata') is not None:
            pt['metadata'] = json.dumps(pt['metadata'])
        if pt.get('notes'):
            pt['notes'] = [Note.to_database_value(n) for n in pt['notes']]
        return pt

class ExtractionSpec(TypedDict):
    """Specification for LLM extraction including queries and schema."""
    id: str
    name: str
    executor: str
    content: dict[str, Any]

    @staticmethod
    def from_database_value(spec: dict[str, Any]) -> "ExtractionSpec":
        spec = {**spec}
        if spec.get("content"):
            spec['content'] = json.loads(spec['content'])
        return spec
    
    @staticmethod
    def to_database_value(spec: "ExtractionSpec") -> dict[str, Any]:
        spec = {**spec}
        if spec.get('content') is not None:
            spec['content'] = json.dumps(spec['content'])
        return spec


class TextRange(TypedDict):
    start_pos: int
    end_pos: int

class SourceCitation(TypedDict):
    # id of the source note
    note_id: str
    # absolutely verbatim quote text (or None if the value is inferred from the entire note or from the metadata)
    verbatim_quote: str | None

class Feedback(TypedDict):
    id: int
    approved: bool
    rejected: bool
    comment: Optional[str]
    created_at: NotRequired[Optional[str]]
    updated_at: NotRequired[Optional[str]]

class ExtractionCitation(TypedDict):
    """A citation linking an extraction to a specific location in a source note."""
    note_id: Optional[str]
    quote: Optional[str]
    char_interval: Optional[TextRange]

class NoteExtraction(TypedDict):
    """LLM extraction output at the level of a phrase of text or a full note/patient response."""
    id: NotRequired[int]
    # Category/type of the extraction
    extraction_class: str
    # Structured information about the extraction
    attributes: dict[str, Optional[str | bool | int | float]] | None
    # Source citations for this extraction
    citations: list[ExtractionCitation]
    # Feedback if applicable
    feedback: NotRequired[Optional[Feedback]]

class ExtractionResult(TypedDict):
    """A collection of extraction results at note- and patient-levels."""
    # ID for the patient for which this result was generated
    patient_id: str
    # Whether or not the extraction spec was run on this patient
    extraction_run: NotRequired[bool]
    # All extractions and responses (responses have char_interval=None)
    extractions: NotRequired[List[NoteExtraction]]

class Project(TypedDict):
    """A set of settings to run extractions in, including source data, base queries, and environment variables."""
    id: int
    name: str
    source_connection: str
    note_metadata_query: Optional[str]
    note_text_query: Optional[str]
    environment_vars: Optional[dict[str, Any]]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    source_read_only: bool

    @staticmethod
    def from_database_value(proj: dict[str, Any]) -> "Project":
        proj = {**proj}
        if proj.get('environment_vars'):
            proj['environment_vars'] = json.loads(proj['environment_vars'])
        return proj
    
    @staticmethod
    def to_database_value(proj: "Project") -> dict[str, Any]:
        proj = {**proj}
        if proj.get('environment_vars') is not None:
            proj['environment_vars'] = json.dumps(proj['environment_vars'])
        return proj


@contextmanager
def project_environment(project: Project):
    """
    Context manager that temporarily sets environment variables defined in a project.

    When activated, it sets the environment variables from the project's environment_vars field.
    After exiting, the environment variables are reset to their original values.

    Args:
        project: Project containing environment_vars field with variable definitions

    Usage:
        with project_environment(project):
            # Environment variables from project are active
            some_operation_that_uses_env_vars()
        # Environment variables are restored to original values
    """
    # Parse environment variables from project
    env_vars = {}
    if project.get('environment_vars'):
        if isinstance(project['environment_vars'], str):
            env_vars = json.loads(project['environment_vars'])
        else:
            env_vars = project['environment_vars']

    # Store original values
    original_values = {}
    vars_to_unset = []

    for key, value in env_vars.items():
        if key in os.environ:
            original_values[key] = os.environ[key]
        else:
            vars_to_unset.append(key)

        # Set the new value
        os.environ[key] = str(value)

    try:
        yield
    finally:
        # Restore original environment
        for key in env_vars.keys():
            if key in original_values:
                os.environ[key] = original_values[key]
            elif key in vars_to_unset:
                os.environ.pop(key, None)


class ExtractionTask(TypedDict):
    id: str
    spec_id: str
    patient_ids: Optional[List[str]]
    status: str
    status_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    progress_current: int
    progress_total: int
    project_id: Optional[int]

    @staticmethod
    def from_database_value(task: dict[str, Any]) -> "ExtractionTask":
        task = {**task}
        if task.get('patient_ids'):
            task['patient_ids'] = json.loads(task['patient_ids'])
        return task
    @staticmethod
    def to_database_value(task: "ExtractionTask") -> dict[str, Any]:
        task = {**task}
        if task.get('patient_ids') is not None:
            task['patient_ids'] = json.dumps(task['patient_ids'])
        return task


class Comment(TypedDict):
    """A comment on a patient or spec."""
    id: int
    annotator_id: int
    username: NotRequired[Optional[str]]
    comment: str
    created_at: str
    updated_at: str
    project_id: NotRequired[Optional[int]]


class PatientComment(Comment):
    """A comment on a patient."""
    patient_id: str


class SpecComment(Comment):
    """A comment on a spec."""
    spec_id: str
