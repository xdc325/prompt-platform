from pydantic import EmailStr, Field

from app.schemas import BaseSchema


class RegisterRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str


class UserResponse(BaseSchema):
    id: str
    email: str
    display_name: str

    model_config = {"from_attributes": True}
