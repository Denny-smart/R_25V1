"""
Authentication API Endpoints
Status checks and user info (Login is handled by Frontend/Supabase directly)
"""

from fastapi import APIRouter, Depends
from typing import Optional
from pydantic import BaseModel

from app.core.auth import require_auth, optional_auth, require_login

router = APIRouter()


class UserResponse(BaseModel):
    """User information response model"""
    id: str
    email: Optional[str]
    is_approved: bool
    role: str
    created_at: Optional[str]


class AuthStatusResponse(BaseModel):
    """Status of the authentication system"""
    enabled: bool
    service: str = "Supabase"


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(require_login)):
    """
    Get current authenticated user information.
    Fails if user is not approved.
    
    **Requires authentication + Admin Approval**
    """
    return UserResponse(**current_user)


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    """
    Get authentication system status
    """
    return {
        "enabled": True,
        "service": "Supabase"
    }


@router.get("/check-approval")
async def check_approval(current_user: Optional[dict] = Depends(optional_auth)):
    """
    Check if the current user is approved. 
    Use this on the frontend to decide whether to show the "Pending Approval" screen.
    Does NOT raise 403.
    """
    if not current_user:
        return {"authenticated": False, "approved": False}
    
    return {
        "authenticated": True,
        "approved": current_user.get("is_approved", False),
        "email": current_user.get("email")
    }