"""Patients router for reading and writing patients, notes, patient comments, and tags."""

import os
import json
import csv
import io
import traceback
from datetime import datetime, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from libretto.database import LLMExtractDatabase
from libretto.types import Project, PatientComment, Patient
from libretto.source_database import SourceDatabase, EditableSourceDatabase, DEFAULT_NOTE_METADATA_QUERY, DEFAULT_NOTE_TEXT_QUERY

from .auth import get_current_user, UserInfo
from .projects import get_project_info


# Request models
class TagRequest(BaseModel):
    patient_ids: List[str]
    tag: str
    action: str  # 'add' or 'remove'


class PatientsUploadRequest(BaseModel):
    patients: List[Patient]


class CommentRequest(BaseModel):
    """Request model for creating or updating comments."""
    comment: str


router = APIRouter(tags=["patients"])

# Global database connection (will be set from main app)
db: Optional[LLMExtractDatabase] = None


def set_database(database: LLMExtractDatabase):
    """Set the global database connection."""
    global db
    db = database


def parse_csv_patients(content: bytes) -> List[Patient]:
    """Parse CSV content and convert to Patient objects."""
    content_str = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(content_str))

    # Expected columns: patient_id, patient_metadata (optional), note_id, note_metadata (optional), note_text
    required_columns = ['patient_id', 'note_id', 'note_text']

    # Check if required columns exist
    if not csv_reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no headers")

    missing_columns = [col for col in required_columns if col not in csv_reader.fieldnames]
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {', '.join(missing_columns)}"
        )

    # Group notes by patient
    patients_dict = {}

    for i, row in enumerate(csv_reader):
        try:
            patient_id = row['patient_id']
            if not patient_id:
                continue

            if patient_id not in patients_dict:
                patients_dict[patient_id] = {
                    'id': patient_id,
                    'metadata': json.loads(row.get('patient_metadata', '{}')) if row.get('patient_metadata') else {},
                    'notes': []
                }

            # Add note if note_id exists
            if row.get('note_id'):
                note = {
                    'id': row['note_id'],
                    'metadata': json.loads(row.get('note_metadata', '{}')) if row.get('note_metadata') else {},
                    'date': row.get('note_date') or row.get('date'),
                    'note_text': row.get('note_text', '')
                }
                patients_dict[patient_id]['notes'].append(note)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=f"Error while parsing row {i + 1} of uploaded CSV file: {e}")

    return list(patients_dict.values())


@router.post("/api/projects/{project_id}/patients/upload")
async def upload_patients_file(
    project_id: int,
    file: UploadFile = File(...),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Upload patients from CSV or JSON file."""
    # Check if database editing is allowed for this project
    if project['source_read_only']:
        raise HTTPException(
            status_code=403,
            detail="Project database is in read-only mode. Cannot modify patients."
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()

    # Parse based on file extension
    filename_lower = file.filename.lower()

    if filename_lower.endswith('.csv'):
        patients = parse_csv_patients(content)
    elif filename_lower.endswith('.json'):
        try:
            json_data = json.loads(content.decode('utf-8'))
            if not isinstance(json_data, list):
                raise HTTPException(status_code=400, detail="JSON file must contain a list of Patient objects")
            patients = json_data
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    else:
        raise HTTPException(
            status_code=400,
            detail="File must be CSV or JSON format. Supported extensions: .csv, .json"
        )

    if not patients:
        raise HTTPException(status_code=400, detail="No valid patients found in file")

    # Remove extractions if these patients have been previously uploaded
    db.clear_existing_results(None, patient_ids=[p["id"] for p in patients], project_id=project['id'])

    try:
        editable_db = EditableSourceDatabase(connection_string=project['source_connection'])
        editable_db.insert_patients(patients, overwrite=True)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error while adding patients to database: {e}")

    return {
        "success": True,
        "message": f"Successfully uploaded and inserted {len(patients)} patients from {file.filename}",
        "patient_ids": [p["id"] for p in patients]
    }


@router.get("/api/projects/{project_id}/patients/download")
async def download_patients(
    project_id: int,
    patientIDs: Optional[str] = Query(None, description="Comma-separated list of patient IDs to export"),
    format: str = Query("csv", description="Export format: 'csv' or 'json'"),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Download patients/notes in CSV or JSON format."""

    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")

    # Parse patient IDs if provided
    patient_ids_list = None
    if patientIDs:
        patient_ids_list = [pid.strip() for pid in patientIDs.split(',') if pid.strip()]
        if not patient_ids_list:
            raise HTTPException(status_code=400, detail="No valid patient IDs provided")

    # Connect to the source database for this project
    source_db = SourceDatabase(connection_string=project['source_connection'])

    # Use project-specific queries or defaults to get full patient data
    query_spec = {
        "note_metadata_query": project.get("note_metadata_query") or DEFAULT_NOTE_METADATA_QUERY,
        "note_text_query": project.get("note_text_query") or DEFAULT_NOTE_TEXT_QUERY
    }

    # Get patients with full note data
    patients = source_db.get_notes(query_spec)

    # Filter by patient IDs if specified
    if patient_ids_list:
        patients = [p for p in patients if p['id'] in patient_ids_list]

    if not patients:
        raise HTTPException(status_code=404, detail="No patients found with the specified IDs")

    timestamp = datetime.now(timezone.utc).isoformat()[:19].replace(':', '-')

    if format == "csv":
        # Generate CSV format
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['patient_id', 'patient_metadata', 'note_id', 'note_metadata', 'note_text'])

        # Write data
        for patient in patients:
            patient_metadata = json.dumps(patient.get('metadata', {})) if patient.get('metadata') else ''

            if patient.get('notes'):
                for note in patient['notes']:
                    note_metadata = json.dumps(note.get('metadata', {})) if note.get('metadata') else ''
                    writer.writerow([
                        patient['id'],
                        patient_metadata,
                        note.get('id', ''),
                        note_metadata,
                        note.get('note_text', '')
                    ])
            else:
                # Patient with no notes
                writer.writerow([
                    patient['id'],
                    patient_metadata,
                    '',
                    '',
                    ''
                ])

        # Generate filename
        patient_count = len(patients)
        if patientIDs:
            filename = f"patients_export_{patient_count}_patients_{timestamp}.csv"
        else:
            filename = f"patients_export_all_{patient_count}_patients_{timestamp}.csv"

        # Return CSV file
        def generate():
            yield output.getvalue().encode('utf-8')

        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache"
            }
        )

    else:  # format == "json"
        # Generate JSON format (list of Patient objects)
        export_data = patients

        # Generate filename
        patient_count = len(patients)
        if patientIDs:
            filename = f"patients_export_{patient_count}_patients_{timestamp}.json"
        else:
            filename = f"patients_export_all_{patient_count}_patients_{timestamp}.json"

        # Return JSON file
        def generate():
            yield json.dumps(export_data, indent=2).encode('utf-8')

        return StreamingResponse(
            generate(),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache"
            }
        )


@router.get("/api/projects/{project_id}/patients")
async def get_patients(
    project_id: int,
    specID: Optional[str] = Query(None),
    full: bool = Query(False),
    search: Optional[str] = Query(None),
    searchTarget: Optional[Literal["all", "text", "metadata", "id"]] = "all",
    metadata_filters: Optional[str] = Query(None, description="JSON-encoded metadata filters"),
    extraction_filters: Optional[str] = Query(None, description="JSON-encoded extraction filters"),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> List[Patient]:
    """Get notes/patients for the project. Supports searching through patient/note metadata and note text (if full=1)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Connect to the source database for this project
    source_db = SourceDatabase(connection_string=project['source_connection'])

    # Use project-specific queries or defaults
    note_metadata_query = project.get("note_metadata_query") or os.getenv("NOTE_METADATA_QUERY", DEFAULT_NOTE_METADATA_QUERY)
    note_text_query = project.get("note_text_query") or os.getenv("NOTE_TEXT_QUERY", DEFAULT_NOTE_TEXT_QUERY)

    # Create a spec-like object with the queries for the source database
    query_spec = {
        "note_metadata_query": note_metadata_query,
        "note_text_query": note_text_query
    }

    if not note_metadata_query or (full and not note_text_query):
        return []

    # Parse and validate filters
    filtered_patient_ids = None

    # Parse metadata filters
    parsed_metadata_filters = []
    if metadata_filters:
        try:
            from libretto.filter_types import validate_filter_request
            metadata_filter_data = json.loads(metadata_filters)
            if isinstance(metadata_filter_data, list):
                # Handle direct list of filters for backwards compatibility
                parsed_metadata_filters = metadata_filter_data
            elif isinstance(metadata_filter_data, dict) and "metadata_filters" in metadata_filter_data:
                # Handle structured filter request
                filter_request = validate_filter_request(metadata_filter_data)
                parsed_metadata_filters = filter_request.get("metadata_filters", [])
            else:
                raise ValueError("metadata_filters must be a list of filters or a structured filter request")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid metadata_filters parameter: {str(e)}")

    # Parse extraction filters
    parsed_extraction_filters = []
    if extraction_filters:
        try:
            from libretto.filter_types import validate_filter_request
            extraction_filter_data = json.loads(extraction_filters)
            if isinstance(extraction_filter_data, list):
                # Handle direct list of filters for backwards compatibility
                parsed_extraction_filters = extraction_filter_data
            elif isinstance(extraction_filter_data, dict) and "extraction_filters" in extraction_filter_data:
                # Handle structured filter request
                filter_request = validate_filter_request(extraction_filter_data)
                parsed_extraction_filters = filter_request.get("extraction_filters", [])
            else:
                raise ValueError("extraction_filters must be a list of filters or a structured filter request")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid extraction_filters parameter: {str(e)}")

    # Apply filters to get patient IDs
    if parsed_metadata_filters or parsed_extraction_filters:
        metadata_patient_ids = set()
        extraction_patient_ids = set()

        # Get patient IDs from metadata filters
        if parsed_metadata_filters:
            try:
                metadata_patient_ids = set(source_db.get_patients_with_metadata_filters(
                    query_spec, parsed_metadata_filters
                ))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error applying metadata filters: {str(e)}")

        # Get patient IDs from extraction filters
        if parsed_extraction_filters:
            try:
                extraction_patient_ids = set(db.get_patients_with_extraction_filters(
                    parsed_extraction_filters, project_id=project['id']
                ))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error applying extraction filters: {str(e)}")

        # Intersect the results (AND logic)
        if parsed_metadata_filters and parsed_extraction_filters:
            # Both filter types - intersect them
            filtered_patient_ids = list(metadata_patient_ids.intersection(extraction_patient_ids))
        elif parsed_metadata_filters:
            # Only metadata filters
            filtered_patient_ids = list(metadata_patient_ids)
        elif parsed_extraction_filters:
            # Only extraction filters
            filtered_patient_ids = list(extraction_patient_ids)

        # If no patients match the filters, return empty
        if filtered_patient_ids is not None and len(filtered_patient_ids) == 0:
            return []

    if search and search.strip():
        # Database-level filtering
        notes = source_db.search_notes(
            spec=query_spec,
            search=search,
            search_target=searchTarget,
            patient_ids=filtered_patient_ids,
            full=full
        )
        if not full:
            notes = [n for n in notes if n.get("note_count", 0) > 0]
    else:
        if full:
            notes = source_db.get_notes(query_spec, patient_ids=filtered_patient_ids)
        else:
            notes = source_db.get_note_metadata(query_spec, patient_ids=filtered_patient_ids, counts_only=True)
            notes = [n for n in notes if n.get("note_count", 0) > 0]

    # Sort by ID by default
    notes = sorted(notes, key=lambda x: x["id"])

    # Add tags to each patient
    if notes:
        patient_ids = [patient['id'] for patient in notes]
        tags_dict = db.get_tags_for_patients(patient_ids, project_id=project['id'])

        for patient in notes:
            patient['tags'] = tags_dict.get(patient['id'], [])

    # Add extraction counts if a spec ID is provided
    if specID and notes:
        extraction_counts = db.get_extraction_counts(specID)
        extracted_patients = db.list_completed_extraction_patients(project_id, specID)
        for patient in notes:
            patient['extraction_count'] = extraction_counts.get(patient['id'], 0)
            patient['extraction_run'] = patient['id'] in extracted_patients

    return notes


@router.get("/api/projects/{project_id}/patients/test")
def check_read_only_mode(
    project_id: int,
    project: Project = Depends(get_project_info)
):
    """Check if database editing is allowed for this project."""
    if project['source_read_only']:
        raise HTTPException(
            status_code=403,
            detail="Project database is in read-only mode. Cannot modify patients."
        )

    # Check if custom queries are set (which makes editing not supported)
    note_metadata_query = project.get("note_metadata_query")
    note_text_query = project.get("note_text_query")

    if (note_metadata_query and note_metadata_query != DEFAULT_NOTE_METADATA_QUERY) or \
       (note_text_query and note_text_query != DEFAULT_NOTE_TEXT_QUERY):
        raise HTTPException(
            status_code=403,
            detail="Custom metadata/text queries are set. Cannot modify patients when using custom queries."
        )

    return { "success": True }


@router.get("/api/projects/{project_id}/patients/{patient_id}")
async def get_patient(
    project_id: int,
    patient_id: str,
    specID: Optional[str] = Query(None),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> Patient:
    """Get details for a specific patient."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Connect to the source database for this project
    source_db = SourceDatabase(connection_string=project['source_connection'])

    # Use project-specific queries or defaults
    note_metadata_query = project.get("note_metadata_query") or os.getenv("NOTE_METADATA_QUERY", DEFAULT_NOTE_METADATA_QUERY)
    note_text_query = project.get("note_text_query") or os.getenv("NOTE_TEXT_QUERY", DEFAULT_NOTE_TEXT_QUERY)

    # Create a spec-like object with the queries for the source database
    query_spec = {
        "note_metadata_query": note_metadata_query,
        "note_text_query": note_text_query
    }

    if not note_metadata_query or not note_text_query:
        return []

    # Get notes using the source database
    notes = source_db.get_notes(query_spec, patient_ids=[patient_id])
    if not notes:
        raise HTTPException(status_code=404, detail="No patient found with that ID")

    # Add tags to each patient
    patient_ids = [patient['id'] for patient in notes]
    tags_dict = db.get_tags_for_patients(patient_ids, project_id=project['id'])

    for patient in notes:
        patient['tags'] = tags_dict.get(patient['id'], [])

    # Add extraction counts if a spec ID is provided
    if specID and notes:
        extraction_counts = db.get_extraction_counts(specID)
        for patient in notes:
            patient['extraction_count'] = extraction_counts.get(patient['id'], 0)

    return notes[0]


@router.post("/api/projects/{project_id}/patients")
async def create_patients(
    project_id: int,
    patients_request: PatientsUploadRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Insert a list of Patient objects into the database."""
    # Check if database editing is allowed for this project
    if project['source_read_only']:
        raise HTTPException(
            status_code=403,
            detail="Project database is in read-only mode. Cannot modify patients."
        )

    if not patients_request.patients:
        return {
            "success": True,
            "message": "",
            "patient_ids": []
        }

    # Remove extractions if these patients have been previously uploaded
    db.clear_existing_results(None, patient_ids=[p["id"] for p in patients_request.patients], project_id=project['id'])

    try:
        editable_db = EditableSourceDatabase(connection_string=project['source_connection'])
        editable_db.insert_patients(patients_request.patients, overwrite=True)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error while adding patients to database: {e}")

    return {
        "success": True,
        "message": f"Successfully inserted {len(patients_request.patients)} patients",
        "patient_ids": [p["id"] for p in patients_request.patients]
    }


@router.delete("/api/projects/{project_id}/patients")
async def delete_patients(
    project_id: int,
    patientIDs: str = Query(..., description="Comma-separated list of patient IDs to delete"),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Delete patients by their IDs."""
    # Check if database editing is allowed for this project
    if project['source_read_only']:
        raise HTTPException(
            status_code=403,
            detail="Project database is in read-only mode. Cannot modify patients."
        )

    patient_ids = [pid.strip() for pid in patientIDs.split(',') if pid.strip()]

    if not patient_ids:
        return {
            "success": True,
            "message": "",
            "patient_ids": []
        }

    editable_db = EditableSourceDatabase(connection_string=project['source_connection'])
    editable_db.delete_patients(patient_ids)

    return {
        "success": True,
        "message": f"Successfully deleted {len(patient_ids)} patients",
        "patient_ids": patient_ids
    }


# Patient comments endpoints
@router.get("/api/projects/{project_id}/patients/{patient_id}/comments")
async def get_patient_comments(
    project_id: int,
    patient_id: str,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> List[PatientComment]:
    """Get all comments for a patient."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    comments = db.get_patient_comments(patient_id, project_id=project['id'])
    return comments


@router.post("/api/projects/{project_id}/patients/{patient_id}/comments")
async def create_patient_comment(
    project_id: int,
    patient_id: str,
    comment_request: CommentRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> PatientComment:
    """Create a new comment for a patient."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    comment_id = db.create_patient_comment(
        patient_id=patient_id,
        annotator_id=current_user.id,
        comment=comment_request.comment,
        project_id=project['id']
    )

    # Return the created comment
    comment = db.get_patient_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=500, detail="Failed to create comment")

    return comment


@router.put("/api/projects/{project_id}/patients/{patient_id}/comments/{comment_id}")
async def update_patient_comment(
    project_id: int,
    patient_id: str,
    comment_id: int,
    comment_request: CommentRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> PatientComment:
    """Update a patient comment. Only the comment author can update it."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if comment exists and belongs to the user
    existing_comment = db.get_patient_comment_by_id(comment_id)
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment['annotator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot update this comment")

    if existing_comment['patient_id'] != patient_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this patient")

    # Validate project access
    if existing_comment.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Comment does not belong to this project")

    new_comment_id = db.update_patient_comment(comment_id, comment_request.comment, current_user.id)
    if new_comment_id is None:
        raise HTTPException(status_code=500, detail="Failed to update comment")

    # Return the updated comment
    comment = db.get_patient_comment_by_id(new_comment_id)
    return comment


@router.delete("/api/projects/{project_id}/patients/{patient_id}/comments/{comment_id}")
async def delete_patient_comment(
    project_id: int,
    patient_id: str,
    comment_id: int,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Delete a patient comment. Only the comment author can delete it."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if comment exists and belongs to the user
    existing_comment = db.get_patient_comment_by_id(comment_id)
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment['annotator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete this comment")

    if existing_comment['patient_id'] != patient_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this patient")

    # Validate project access
    if existing_comment.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Comment does not belong to this project")

    success = db.delete_patient_comment(comment_id, current_user.id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete comment")

    return {"success": True, "message": "Comment deleted successfully"}


# Tags endpoints
@router.post("/api/projects/{project_id}/tags")
async def manage_tags(
    project_id: int,
    tag_request: TagRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Add or remove tags for a list of patient IDs."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not tag_request.patient_ids:
        raise HTTPException(status_code=400, detail="patient_ids cannot be empty")

    if not tag_request.tag:
        raise HTTPException(status_code=400, detail="tag cannot be empty")

    if tag_request.action not in ['add', 'remove']:
        raise HTTPException(status_code=400, detail="action must be 'add' or 'remove'")

    try:
        if tag_request.action == 'add':
            db.add_tag_to_patients(tag_request.patient_ids, tag_request.tag, project_id=project['id'])
        elif tag_request.action == 'remove':
            db.remove_tag_from_patients(tag_request.patient_ids, tag_request.tag, project_id=project['id'])

        return {
            "success": True,
            "message": f"Tag '{tag_request.tag}' {tag_request.action}ed for {len(tag_request.patient_ids)} patients"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to {tag_request.action} tag: {str(e)}")