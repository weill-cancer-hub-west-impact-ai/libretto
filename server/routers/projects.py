"""Projects router for listing and managing projects."""

import os
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from libretto.database import LLMExtractDatabase
from libretto.types import Project

from .auth import get_current_user, UserInfo, get_current_admin_user


router = APIRouter(prefix="/api/projects", tags=["projects"])

# Global database connection (will be set from main app)
db: Optional[LLMExtractDatabase] = None


def set_database(database: LLMExtractDatabase):
    """Set the global database connection."""
    global db
    db = database


async def get_project_info(project_id: int, current_user: UserInfo = Depends(get_current_user)) -> Project:
    """Get project information and validate user access."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    project = db.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check authentication requirements
    if os.getenv("AUTH_ENABLED", "0") == "1":
        # Authentication is enabled, check user access
        if not db.user_has_project_access(current_user.id, project_id):
            raise HTTPException(status_code=403, detail="Access denied to this project")

    return project

# Request/Response models
class CreateProjectRequest(BaseModel):
    name: str
    source_connection: str
    source_read_only: bool = False
    note_metadata_query: Optional[str] = None
    note_text_query: Optional[str] = None
    environment_vars: Optional[dict] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    source_connection: Optional[str] = None
    source_read_only: Optional[bool] = None
    note_metadata_query: Optional[str] = None
    note_text_query: Optional[str] = None
    environment_vars: Optional[dict] = None


class AddUserToProjectRequest(BaseModel):
    user_id: int


@router.get("", response_model=List[Project])
async def list_projects(
    all: bool = Query(False, description="Return all projects (admin only)"),
    current_user: UserInfo = Depends(get_current_user)
):
    """List available projects for the current user."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if os.getenv("AUTH_ENABLED", "0") == "1":
        # Authentication is enabled
        if all:
            # Admin-only: return all projects
            if not current_user.is_admin:
                raise HTTPException(status_code=403, detail="Admin access required to list all projects")
            projects = db.list_projects()
        else:
            # Return user's projects
            projects = db.list_projects(user_id=current_user.id)
    else:
        # No authentication, return all projects
        projects = db.list_projects()
    return [{**p, "environment_vars": None} for p in projects]


@router.post("", response_model=Project)
async def create_project(
    request: CreateProjectRequest,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Create a new project (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Create project data
    project_data: Project = {
        "id": 0,  # Will be set by database
        "name": request.name,
        "source_connection": request.source_connection,
        "source_read_only": request.source_read_only,
        "note_metadata_query": request.note_metadata_query,
        "note_text_query": request.note_text_query,
        "environment_vars": request.environment_vars
    }

    try:
        project_id = db.create_project(project_data)
        created_project = db.get_project_by_id(project_id)
        if not created_project:
            raise HTTPException(status_code=500, detail="Failed to retrieve created project")
        return {**created_project, "environment_vars": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: int,
    request: UpdateProjectRequest,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Update a project (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Get existing project
    existing_project = db.get_project_by_id(project_id)
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update only provided fields
    updated_data: Project = {**existing_project}
    if request.name is not None:
        updated_data["name"] = request.name
    if request.source_connection is not None:
        updated_data["source_connection"] = request.source_connection
    if request.source_read_only is not None:
        updated_data["source_read_only"] = request.source_read_only
    if request.note_metadata_query is not None:
        updated_data["note_metadata_query"] = request.note_metadata_query
    if request.note_text_query is not None:
        updated_data["note_text_query"] = request.note_text_query
    if request.environment_vars is not None:
        updated_data["environment_vars"] = request.environment_vars

    try:
        success = db.update_project(project_id, updated_data)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")

        updated_project = db.get_project_by_id(project_id)
        if not updated_project:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated project")
        return {**updated_project, "environment_vars": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Delete a project (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if project exists
    existing_project = db.get_project_by_id(project_id)
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        success = db.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


@router.get("/{project_id}/users")
async def list_project_users(
    project_id: int,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """List users in a project (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if project exists
    existing_project = db.get_project_by_id(project_id)
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        users = db.get_users_in_project(project_id)
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list project users: {str(e)}")


@router.post("/{project_id}/users")
async def add_user_to_project(
    project_id: int,
    request: AddUserToProjectRequest,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Add a user to a project (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if project exists
    existing_project = db.get_project_by_id(project_id)
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user exists
    user = db.get_user_by_id(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = db.add_user_to_project(request.user_id, project_id)
        if not success:
            raise HTTPException(status_code=409, detail="User is already in this project")
        return {"message": "User added to project successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add user to project: {str(e)}")


@router.delete("/{project_id}/users/{user_id}")
async def remove_user_from_project(
    project_id: int,
    user_id: int,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Remove a user from a project (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if project exists
    existing_project = db.get_project_by_id(project_id)
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user exists
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = db.remove_user_from_project(user_id, project_id)
        if not success:
            raise HTTPException(status_code=404, detail="User is not in this project")
        return {"message": "User removed from project successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove user from project: {str(e)}")