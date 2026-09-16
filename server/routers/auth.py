"""Authentication router for user login and authentication management."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import List

from libretto.database import LLMExtractDatabase


# Authentication models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool


class UserInfo(BaseModel):
    id: int
    username: str
    created_at: str
    last_login: Optional[str] = None
    is_admin: bool = False


# Authentication configuration
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "1440"))  # 24 hours

security = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# Global database connection (will be set from main app)
db: Optional[LLMExtractDatabase] = None


def set_database(database: LLMExtractDatabase):
    """Set the global database connection."""
    global db
    db = database


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed.encode("utf-8"),
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with username and password."""
    if not db:
        return None

    user = db.get_user_by_username(username)
    if not user:
        return None

    if os.getenv("AUTH_ENABLED", "0") == "1" and not verify_password(password, user["password_hash"]):
        return None

    return user


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserInfo:
    """Get current authenticated user."""
    if os.getenv("AUTH_ENABLED", "0") != "1":
        # Return dummy user when auth is disabled
        return UserInfo(id=1, username="anonymous", created_at=datetime.now(timezone.utc).isoformat())

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    user = db.get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserInfo(**user)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login timestamp
    db.update_user_last_login(user["id"])

    if os.getenv("AUTH_ENABLED", "0") == "1":
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )
    else:
        access_token = ""

    return LoginResponse(
        access_token=access_token,
        username=user["username"],
        is_admin=user["is_admin"]
    )


@router.post("/logout")
async def logout(current_user: UserInfo = Depends(get_current_user)):
    """Logout user (token will expire naturally)."""
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: UserInfo = Depends(get_current_user)):
    """Get current user information."""
    return current_user


async def get_current_admin_user(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Dependency to ensure current user is an admin."""
    if os.getenv("AUTH_ENABLED", "0") == "1" and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# Request/Response models for user management
class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    password: Optional[str] = None
    is_admin: Optional[bool] = None



# User management endpoints
@router.get("/users", response_model=List[UserInfo])
async def list_users(current_user: UserInfo = Depends(get_current_admin_user)):
    """List all users (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        users = db.list_users()
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.post("/users", response_model=UserInfo)
async def create_user(
    request: CreateUserRequest,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Create a new user (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if username already exists
    existing_user = db.get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")

    try:
        password_hash = get_password_hash(request.password)
        user_id = db.create_user(request.username, password_hash, request.is_admin)

        created_user = db.get_user_by_id(user_id)
        if not created_user:
            raise HTTPException(status_code=500, detail="Failed to retrieve created user")

        return UserInfo(**created_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@router.put("/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Update a user (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if user exists
    existing_user = db.get_user_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # Update password if provided
        if request.password is not None:
            password_hash = get_password_hash(request.password)
            db.update_user_password(user_id, password_hash)

        # Update admin privileges if provided
        if request.is_admin is not None:
            db.update_user_privileges(user_id, request.is_admin)

        updated_user = db.get_user_by_id(user_id)
        if not updated_user:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated user")

        return UserInfo(**updated_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: UserInfo = Depends(get_current_admin_user)
):
    """Delete a user (admin only)."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Check if user exists
    existing_user = db.get_user_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = db.delete_user(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")

        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.put("/me/password")
async def update_own_password(
    request: UpdateUserRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """Update current user's password."""
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Get current user with password hash
    user_with_password = db.get_user_by_id(current_user.id)
    if not user_with_password:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        new_password_hash = get_password_hash(request.password)
        db.update_user_password(current_user.id, new_password_hash)
        return {"message": "Password updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update password: {str(e)}")