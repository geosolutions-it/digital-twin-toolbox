from pydantic import EmailStr
from sqlmodel import Field

from app.models.user_db import User, UserBase


# Only the schema needed to seed the single implicit user (see core/db.py:init_db).
class UserCreate(UserBase):
    email: EmailStr = Field(max_length=255)  # type: ignore
    password: str = Field(min_length=8, max_length=40)


__all__ = [
    "User", "UserBase", "UserCreate",
]
