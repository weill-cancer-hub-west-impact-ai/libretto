"""Extractions router for creating and managing extraction tasks and retrieving results."""

import os
import json
import uuid
import pandas as pd
from datetime import datetime, timezone
from typing import Optional, List, Literal

import redis
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from libretto.database import LLMExtractDatabase
from libretto.types import Project, ExtractionResult, ExtractionSpec

from .auth import get_current_user, UserInfo
from .projects import get_project_info


# Request models
class FeedbackRequest(BaseModel):
    extraction_id: Optional[int] = None
    approved: bool
    rejected: bool
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    message: str


class TaskRequest(BaseModel):
    specID: str
    patientIDs: Optional[List[str]] = None
    overwrite: bool = False


class TaskActionRequest(BaseModel):
    action: str


class ResultsRequest(BaseModel):
    specs: List[ExtractionSpec]
    patientID: str


router = APIRouter(tags=["extractions"])

# Global database and Redis connections (will be set from main app)
db: Optional[LLMExtractDatabase] = None
redis_client: Optional[redis.Redis] = None


def set_database(database: LLMExtractDatabase):
    """Set the global database connection."""
    global db
    db = database


def set_redis_client(client: redis.Redis):
    """Set the global Redis client."""
    global redis_client
    redis_client = client


# Feedback endpoints
@router.post("/api/projects/{project_id}/feedback", response_model=FeedbackResponse)
async def create_feedback(
    project_id: int,
    feedback: FeedbackRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Save feedback for extraction or response."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not feedback.extraction_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide extraction_id"
        )

    if feedback.approved and feedback.rejected:
        raise HTTPException(
            status_code=400,
            detail="approved and rejected cannot both be true"
        )

    feedback_id = db.insert_feedback({
        'annotator_id': current_user.id,
        'extraction_id': feedback.extraction_id,
        'approved': feedback.approved,
        'rejected': feedback.rejected,
        'comment': feedback.comment
    }, project_id=project['id'])

    return FeedbackResponse(
        id=feedback_id,
        message="Feedback saved successfully"
    )


# Prompt history endpoints
@router.get("/api/projects/{project_id}/prompt_history")
async def get_prompt_history(
    project_id: int,
    type: Optional[str] = Query(None),
    spec_id: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Get prompt history, optionally filtered by type and/or spec_id."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # If spec_id is provided, validate it belongs to this project
    if spec_id:
        spec = db.get_spec_by_id(spec_id)
        if not spec or spec.get('project_id') != project['id']:
            raise HTTPException(status_code=403, detail="Spec does not belong to this project")

    history = db.list_prompt_history(
        type_filter=type,
        spec_id_filter=spec_id,
        limit=limit
    )
    return history


# Tasks endpoints
@router.get("/api/projects/{project_id}/tasks")
async def get_tasks(
    project_id: int,
    specID: Optional[str] = Query(None),
    patientID: Optional[str] = Query(None),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """List/search extraction tasks."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not specID and not patientID:
        return db.list_extraction_tasks(project_id=project["id"])

    task = db.find_running_extraction_task({
        'specID': specID,
        'patientID': patientID
    })
    if not task:
        raise HTTPException(status_code=404, detail="The task does not exist")
    return task


@router.post("/api/projects/{project_id}/tasks")
async def create_task(
    project_id: int,
    task_request: TaskRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Create extraction task."""
    if not db or not redis_client:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not task_request.specID:
        raise HTTPException(status_code=400, detail="Spec ID is required")

    # Validate spec belongs to this project
    spec = db.get_spec_by_id(task_request.specID)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Spec with ID {task_request.specID} does not exist")
    if spec.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Spec does not belong to this project")

    task_id = str(uuid.uuid4())
    db.create_extraction_task(task_id, task_request.specID, task_request.patientIDs, project_id=project['id'])

    # Publish to Redis
    queue_name = os.getenv('QUEUE_NAME', 'extraction_tasks')
    redis_client.publish(
        queue_name,
        json.dumps({
            'task_id': task_id,
            'spec_id': task_request.specID,
            'patient_ids': task_request.patientIDs,
            'overwrite': task_request.overwrite,
            'project_id': project['id']
        })
    )

    task = db.get_extraction_task(task_id)
    return task


@router.get("/api/projects/{project_id}/tasks/{task_id}")
async def get_task_by_id(
    project_id: int,
    task_id: str,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Get task by ID."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    task = db.get_extraction_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="The task does not exist")

    # Validate task belongs to this project
    if task.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Task does not belong to this project")

    return task


@router.patch("/api/projects/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: int,
    task_id: str,
    action_request: TaskActionRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Update task (currently only supports cancel action)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Validate task belongs to this project
    task = db.get_extraction_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="The task does not exist")
    if task.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Task does not belong to this project")

    if action_request.action == 'cancel':
        success = db.cancel_task(task_id)
        if success:
            updated_task = db.get_extraction_task(task_id)
            return updated_task
        else:
            raise HTTPException(
                status_code=400,
                detail="Task cannot be canceled (not found or already completed)"
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid action")


# Results endpoints
@router.post("/api/projects/{project_id}/results")
async def get_results(
    project_id: int,
    results_request: ResultsRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> List[ExtractionResult]:
    """Get existing extraction results."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not results_request.patientID:
        raise HTTPException(
            status_code=400,
            detail="patientID must be provided. To return all data, use the /api/projects/{project_id}/results/download endpoint."
        )

    results = []
    for source in results_request.specs:
        result = db.get_existing_results(source, results_request.patientID, project_id=project['id'])
        results.append(result)

    return results


@router.get("/api/projects/{project_id}/results/extraction_classes")
async def get_extraction_metadata(
    project_id: int,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Return available extraction classes and attributes for filtering."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        extraction_specs = db.get_available_extraction_classes_and_attributes(project_id=project['id'])

        return {
            "extraction_specs": extraction_specs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving extraction metadata: {str(e)}")


@router.get("/api/projects/{project_id}/results/download")
async def download_results(
    project_id: int,
    patient_id: Optional[str] = Query(None),
    spec_ids: Optional[str] = Query(None),
    format: Literal["csv", "json"] = Query("json"),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Download results as JSON file."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if spec_ids is not None:
        spec_ids = spec_ids.split(",")
        sources = [db.get_spec_by_id(id) for id in spec_ids]
        sources = [s for s in sources if s is not None]
    else:
        sources = None

    # Get results
    results = {}
    if sources is not None:
        for source in sources:
            if patient_id is not None:
                results.setdefault(patient_id, { "patient_id": patient_id, "extractions": [] })
                results[patient_id]["extractions"].extend(db.get_existing_results(source, patient_id, project_id=project['id'])["extractions"])
            else:
                source_results = db.get_existing_results(source, None, project_id=project['id'])
                for patient_id, patient_results in source_results.items():
                    results.setdefault(patient_id, { "patient_id": patient_id, "extractions": [] })
                    results[patient_id]["extractions"].extend(patient_results["extractions"])
    else:
        if patient_id is not None:
            results = {patient_id: db.get_existing_results(None, patient_id, project_id=project['id'])}
        else:
            results = db.get_existing_results(None, None, project_id=project['id'])

    # Create export data
    if format == "csv":
        export_data = pd.DataFrame([
            {"patient_id": patient_id, **extraction}
            for patient_id, extractions in results.items()
            for extraction in extractions["extractions"]
        ])
        export_data["attributes"] = export_data["attributes"].apply(
            lambda x: json.dumps(x) if x is not None else None
        )
        export_data["citations"] = export_data["citations"].apply(
            lambda x: json.dumps(x) if x is not None else None
        )
        export_data = export_data.drop(columns=["feedback"]).join(
            pd.json_normalize(export_data["feedback"]).reindex(columns=["approved", "rejected", "comment"])
        )
        extension = "csv"
    else:
        export_data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "patient_filter": patient_id or "all",
            "results": results
        }
        extension = "json"

    # Generate filename
    timestamp = datetime.now(timezone.utc).isoformat()[:19].replace(':', '-')
    filename = (
        f"extraction_results_patient_{patient_id}_{timestamp}.{extension}"
        if patient_id
        else f"extraction_results_all_patients_{timestamp}.{extension}"
    )

    # Return as downloadable JSON file
    def generate():
        if format == "csv":
            yield export_data.to_csv()
        else:
            yield json.dumps(export_data, indent=2)

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )
