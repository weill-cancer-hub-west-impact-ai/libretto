"""Specs router for creating, updating, deleting specs and spec comments."""

import os
import json
import asyncio
import traceback
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, AsyncIterator, Callable

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from libretto.database import LLMExtractDatabase
from libretto.types import Project, SpecComment, ExtractionSpec
from libretto.api_helper import setup_llm_api
from libretto.noteextract.generate import NoteExtractSpecGenerator
from libretto.prompt_only.generate import PromptOnlySpecGenerator, PromptOnlyOptionalSpecContent

from .auth import get_current_user, UserInfo
from .projects import get_project_info

logger = logging.getLogger()

# HTTP request models
class GenerateNoteExtractSpecRequest(BaseModel):
    prompt: Optional[str] = None
    message_history: list[dict[str, Any]] = []
    spec_draft: Optional[dict[str, Any]] = None
    evaluate: bool = False
    evaluate_max_passes: int = Field(default=2, ge=2, le=10)

class GeneratePromptOnlySpecRequest(BaseModel):
    prompt: Optional[str] = None
    message_history: list[dict[str, Any]] = []
    spec_draft: Optional[PromptOnlyOptionalSpecContent] = None
    evaluate: bool = False
    evaluate_max_passes: int = Field(default=2, ge=2, le=10)


class CommentRequest(BaseModel):
    """Request model for creating or updating comments."""
    comment: str


router = APIRouter(tags=["specs"])

# Global database connection (will be set from main app)
db: Optional[LLMExtractDatabase] = None


def set_database(database: LLMExtractDatabase):
    """Set the global database connection."""
    global db
    db = database


@router.get("/api/projects/{project_id}/specs")
async def get_specs(
    project_id: int,
    noteID: Optional[str] = Query(None),
    current_only: bool = Query(False),
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Get specs, optionally filtered by noteID. Returns all versions by default unless current_only=True."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    specs = db.get_specs(note_id=noteID, current_only=current_only, project_id=project['id'])
    return specs


@router.get("/api/projects/{project_id}/specs/{spec_id}")
async def get_spec_by_id(
    project_id: int,
    spec_id: str,
    version: Optional[int] = Query(None),
    current_only: bool = Query(False),
    project: Project = Depends(get_project_info)
):
    """Get spec by ID. If version is specified, returns that version. If current_only=True, returns only current version. Default returns all versions for that spec ID."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if version is not None or current_only:
        # Return single spec
        spec = db.get_spec_by_id(spec_id, version=version, current_only=current_only)
        if not spec:
            version_desc = f" version {version}" if version is not None else " (current)"
            raise HTTPException(status_code=404, detail=f"Spec with ID {spec_id}{version_desc} does not exist")
        # Validate project access
        if spec.get('project_id') != project['id']:
            raise HTTPException(status_code=403, detail="Spec does not belong to this project")
        return spec
    else:
        # Return all versions for this spec ID
        specs = db.get_specs(note_id=None, current_only=False, project_id=project['id'])
        spec_versions = [s for s in specs if s['id'] == spec_id]
        if not spec_versions:
            raise HTTPException(status_code=404, detail=f"Spec with ID {spec_id} does not exist")
        return spec_versions


@router.post("/api/projects/{project_id}/specs/{spec_id}")
async def update_spec_by_id(
    project_id: int,
    spec_id: str,
    spec: Dict[str, Any],
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Update spec by ID."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # If no project_id specified, use the one from the endpoint URL
    if spec is None:
        spec = {}
    spec["project_id"] = project['id']
    spec["id"] = spec_id
    spec["is_current"] = True
    spec["parent_version_id"] = None
    if "deleted" in spec: del spec["deleted"]

    new_id = db.update_spec_by_id(spec_id, spec, project_id=project['id'])
    return {"success": True, "spec_id": new_id}


@router.delete("/api/projects/{project_id}/specs/{spec_id}")
async def delete_spec_by_id(
    project_id: int,
    spec_id: str,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Delete spec by ID."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    db.delete_spec_by_id(spec_id, project_id=project['id'])
    return {"success": True}


@router.get("/api/projects/{project_id}/specs/{spec_id}/download")
async def download_spec(
    project_id: int,
    spec_id: str,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Download spec as JSON file."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Get spec by ID (current version only)
    spec = db.get_spec_by_id(spec_id, current_only=True)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Spec with ID {spec_id} does not exist")

    # Validate project access
    if spec.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Spec does not belong to this project")

    # Generate filename
    timestamp = datetime.now(timezone.utc).isoformat()[:19].replace(':', '-')
    safe_spec_name = "".join(c for c in spec.get('name', 'unnamed') if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
    filename = f"spec_{safe_spec_name}_{spec_id}_{timestamp}.json"

    # Return as downloadable JSON file
    def generate():
        yield json.dumps(spec, indent=2).encode('utf-8')

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )


def _sse_event(event: str, data: Any) -> str:
    """Format a server-sent event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _get_existing_spec(spec_id: str, project: Project) -> Optional[dict]:
    """Fetch existing spec and validate project ownership; returns None if not found."""
    try:
        existing_spec = db.get_spec_by_id(spec_id)
        if existing_spec and existing_spec.get('project_id') != project['id']:
            raise HTTPException(status_code=403, detail="Spec does not belong to this project")
        return existing_spec
    except HTTPException:
        raise
    except:
        return None


async def _stream_generate_and_evaluate(generator_async_iter: AsyncIterator, result_transform: Optional[Callable[[dict], dict]] = None):
    """
    Wrap a generate_and_evaluate_* async generator into an SSE string stream.

    The generator yields (event_type, data) tuples; this function formats them
    as SSE events and yields the formatted strings.
    """
    async for event_type, data in generator_async_iter:
        if event_type == "result" and "spec" in data and result_transform is not None:
            data = result_transform(data)

        yield _sse_event(event_type, data)

def make_save_fn(spec_id: str, project: Project, always_overwrite: bool = False) -> Callable[[dict], dict]:
    def _transform_and_save_spec(data: dict) -> dict:
        if not data.get("spec"):
            raise HTTPException(status_code=500, detail="The LLM did not return a spec. Please try again.")
        new_spec = data["spec"]
        response_spec = {**new_spec, "id": spec_id, "project_id": project["id"]}
        new_id = db.update_spec_by_id(spec_id, response_spec, project_id=project["id"], force_overwrite=always_overwrite)
        response_spec = {**response_spec, "id": new_id}
        return {**data, "spec": response_spec}
    return _transform_and_save_spec


@router.post("/api/projects/{project_id}/specs/{spec_id}/generate_noteextract")
async def generate_noteextract_spec_endpoint(
    spec_id: str,
    request: GenerateNoteExtractSpecRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Generate or update a noteextract spec using LLM based on user prompt."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not request or not (request.prompt or request.message_history):
        raise HTTPException(status_code=400, detail="prompt or message_history is required")

    llm_api = setup_llm_api(project, model_name=os.getenv("SPEC_GENERATION_MODEL_ID"))
    existing_spec = _get_existing_spec(spec_id, project)

    generator = NoteExtractSpecGenerator(
        llm_api=llm_api,
        project=project,
        model=os.getenv("SPEC_GENERATION_MODEL_ID"),
    )

    if request.prompt:
        db.add_prompt_history(
            type_str="spec_generation_noteextract",
            prompt=request.prompt,
            spec_id=spec_id,
        )

    if request.evaluate:
        return StreamingResponse(
            _stream_generate_and_evaluate(
                generator.generate_and_evaluate_spec(
                    message_history=request.message_history,
                    prompt=request.prompt,
                    spec_draft=request.spec_draft,
                    existing_spec=existing_spec,
                    evaluate_max_passes=request.evaluate_max_passes,
                ),
                make_save_fn(spec_id, project)
            ),
            media_type="text/event-stream",
        )

    # Non-SSE path
    try:
        result = await asyncio.to_thread(
            generator.generate_spec,
            request.message_history,
            request.prompt,
            request.spec_draft,
            existing_spec
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error occurred while calling LLM: {e}")

    if questions := result.get("questions"):
        return {"questions": questions, "message_history": result["message_history"]}

    response_spec = make_save_fn(spec_id, project)(result)

    return {
        "response_message": result.get("response_message"), 
        "spec": response_spec, 
        "message_history": result["message_history"]
    }


@router.post("/api/projects/{project_id}/specs/{spec_id}/generate_prompt_only")
async def generate_prompt_only_spec_endpoint(
    spec_id: str,
    request: GeneratePromptOnlySpecRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Generate or update a prompt-only spec using LLM based on user prompt."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not request or not (request.prompt or request.message_history):
        raise HTTPException(status_code=400, detail="prompt or message_history is required")

    llm_api = setup_llm_api(project, model_name=os.getenv("SPEC_GENERATION_MODEL_ID"))
    existing_spec = _get_existing_spec(spec_id, project)

    generator = PromptOnlySpecGenerator(
        llm_api=llm_api,
        project=project,
        model=os.getenv("SPEC_GENERATION_MODEL_ID"),
    )

    if request.prompt:
        db.add_prompt_history(
            type_str="spec_generation_prompt_only",
            prompt=request.prompt,
            spec_id=spec_id,
        )

    if request.evaluate:
        return StreamingResponse(
            _stream_generate_and_evaluate(
                generator.generate_and_evaluate_spec(
                    message_history=request.message_history,
                    prompt=request.prompt,
                    spec_draft=request.spec_draft,
                    existing_spec=existing_spec,
                    evaluate_max_passes=request.evaluate_max_passes,
                ),
                make_save_fn(spec_id, project)
            ),
            media_type="text/event-stream",
        )

    # Non-SSE path
    try:
        result = await asyncio.to_thread(
            generator.generate_spec,
            request.message_history,
            request.prompt,
            request.spec_draft,
            existing_spec
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error occurred while calling LLM: {e}")

    if questions := result.get("questions"):
        return {"questions": questions, "message_history": result["message_history"]}

    response_spec = make_save_fn(spec_id, project)(result)

    return {
        "response_message": result.get("response_message"), 
        "spec": response_spec, 
        "message_history": result["message_history"]
    }


# Spec comments endpoints
@router.get("/api/projects/{project_id}/specs/{spec_id}/comments")
async def get_spec_comments(
    project_id: int,
    spec_id: str,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> List[SpecComment]:
    """Get all comments for a spec."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Validate spec belongs to this project
    spec = db.get_spec_by_id(spec_id, current_only=True)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    if spec.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Spec does not belong to this project")

    comments = db.get_spec_comments(spec_id, project_id=project['id'])
    return comments


@router.post("/api/projects/{project_id}/specs/{spec_id}/comments")
async def create_spec_comment(
    project_id: int,
    spec_id: str,
    comment_request: CommentRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> SpecComment:
    """Create a new comment for a spec."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Validate spec belongs to this project
    spec = db.get_spec_by_id(spec_id, current_only=True)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    if spec.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Spec does not belong to this project")

    comment_id = db.create_spec_comment(
        spec_id=spec_id,
        annotator_id=current_user.id,
        comment=comment_request.comment,
        project_id=project['id']
    )

    # Return the created comment
    comment = db.get_spec_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=500, detail="Failed to create comment")

    return comment


@router.put("/api/projects/{project_id}/specs/{spec_id}/comments/{comment_id}")
async def update_spec_comment(
    project_id: int,
    spec_id: str,
    comment_id: int,
    comment_request: CommentRequest,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
) -> SpecComment:
    """Update a spec comment. Only the comment author can update it."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if comment exists and belongs to the user
    existing_comment = db.get_spec_comment_by_id(comment_id)
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment['annotator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot update this comment")

    if existing_comment['spec_id'] != spec_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this spec")

    # Validate project access
    if existing_comment.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Comment does not belong to this project")

    new_comment_id = db.update_spec_comment(comment_id, comment_request.comment, current_user.id)
    if new_comment_id is None:
        raise HTTPException(status_code=500, detail="Failed to update comment")

    # Return the updated comment
    comment = db.get_spec_comment_by_id(new_comment_id)
    return comment


@router.delete("/api/projects/{project_id}/specs/{spec_id}/comments/{comment_id}")
async def delete_spec_comment(
    project_id: int,
    spec_id: str,
    comment_id: int,
    project: Project = Depends(get_project_info),
    current_user: UserInfo = Depends(get_current_user)
):
    """Delete a spec comment. Only the comment author can delete it."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if comment exists and belongs to the user
    existing_comment = db.get_spec_comment_by_id(comment_id)
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment['annotator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete this comment")

    if existing_comment['spec_id'] != spec_id:
        raise HTTPException(status_code=400, detail="Comment does not belong to this spec")

    # Validate project access
    if existing_comment.get('project_id') != project['id']:
        raise HTTPException(status_code=403, detail="Comment does not belong to this project")

    success = db.delete_spec_comment(comment_id, current_user.id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete comment")

    return {"success": True, "message": "Comment deleted successfully"}
