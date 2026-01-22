from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


class UserRegister(BaseModel):
    """Schema for user registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: str  # User email
    exp: Optional[int] = None


class UserResponse(BaseModel):
    """Schema for user data in responses."""
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    roles: List[str] = []

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Schema for login response with user data."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
