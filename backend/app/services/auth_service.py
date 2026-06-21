import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository


@dataclass
class AuthResult:
    """Result of a successful authentication operation."""
    access_token: str
    refresh_token: str
    user: User


class AuthService:
    """Handles user registration, login, token refresh, and profile retrieval."""

    def __init__(self, session: AsyncSession):
        self.user_repo = UserRepository(session)

    async def register(self, email: str, password: str, display_name: str) -> AuthResult:
        """Register a new user account. Raises ConflictError if email already exists."""
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ConflictError("Email already registered")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            display_name=display_name,
        )
        await self.user_repo.create(user)

        return AuthResult(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            user=user,
        )

    async def login(self, email: str, password: str) -> AuthResult:
        """Authenticate a user with email and password. Uses constant-time comparison."""
        user = await self.user_repo.find_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")

        return AuthResult(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            user=user,
        )

    async def refresh(self, refresh_token: str) -> AuthResult:
        """Issue new access + refresh tokens from a valid refresh token (token rotation)."""
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid token type")
            user_id = payload["sub"]
        except ValueError:
            raise UnauthorizedError("Invalid or expired refresh token")

        user = await self.user_repo.find_by_id(uuid.UUID(user_id))
        if not user:
            raise UnauthorizedError("User not found")

        return AuthResult(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            user=user,
        )

    async def get_me(self, user_id: str) -> User:
        """Return the user profile for the given user ID."""
        user = await self.user_repo.find_by_id(uuid.UUID(user_id))
        if not user:
            raise UnauthorizedError("User not found")
        return user
