from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id, get_db
from app.core.exceptions import UnauthorizedError
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix=f"{settings.api_prefix}/auth", tags=["auth"])


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new user account and return access + refresh tokens."""
    svc = AuthService(db)
    result = await svc.register(body.email, body.password, body.display_name)
    _set_refresh_cookie(response, result.refresh_token)
    return {
        "success": True,
        "data": {
            "access_token": result.access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(result.user).model_dump(mode="json"),
        },
        "error": None,
    }


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password, return tokens."""
    svc = AuthService(db)
    result = await svc.login(body.email, body.password)
    _set_refresh_cookie(response, result.refresh_token)
    return {
        "success": True,
        "data": {
            "access_token": result.access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(result.user).model_dump(mode="json"),
        },
        "error": None,
    }


@router.post("/refresh", response_model=dict)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Issue a new access token using the httpOnly refresh token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise UnauthorizedError("No refresh token")

    svc = AuthService(db)
    result = await svc.refresh(refresh_token)
    _set_refresh_cookie(response, result.refresh_token)
    return {
        "success": True,
        "data": {
            "access_token": result.access_token,
            "token_type": "bearer",
        },
        "error": None,
    }


@router.get("/me", response_model=dict)
async def me(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """Return the currently authenticated user's profile."""
    svc = AuthService(db)
    user = await svc.get_me(user_id)
    return {
        "success": True,
        "data": UserResponse.model_validate(user).model_dump(mode="json"),
        "error": None,
    }


def _set_refresh_cookie(response: Response, token: str):
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/api/v1/auth",
        max_age=settings.refresh_token_expire_days * 86400,
    )
