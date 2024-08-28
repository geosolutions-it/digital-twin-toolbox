import uuid

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional
from enum import Enum

# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    assets: list["Asset"] = Relationship(back_populates="owner", cascade_delete=True)
    pipelines: list["Pipeline"] = Relationship(back_populates="owner", cascade_delete=True)

# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int

# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)

# Shared properties
class AssetBase(SQLModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    content_size: int | None = None
    asset_type: str | None = None
    extension: str | None = None
    geometry_type: str | None = None
    upload_id: str | None = None
    upload_status: str | None = None
    upload_result: Optional[dict|None] | None = Field(nullable=True, sa_type=JSONB)

# Database model, database table inferred from class name
class Asset(AssetBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="assets")


# Properties to return via API, id is always required
class AssetPublic(AssetBase):
    id: uuid.UUID
    owner_id: uuid.UUID

class AssetsPublic(SQLModel):
    data: list[AssetPublic]
    count: int

# Shared properties
class PipelineBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    asset_id: uuid.UUID | None
    data: Optional[dict] = Field(nullable=True, sa_type=JSONB)
    task_id: str | None
    task_status: str | None
    task_result: Optional[dict|None] | None = Field(nullable=True, sa_type=JSONB)

# Database model, database table inferred from class name
class Pipeline(PipelineBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="pipelines")

# Properties to return via API, id is always required
class PipelinePublic(PipelineBase):
    id: uuid.UUID
    owner_id: uuid.UUID

# Properties to return via API, id is always required
class PipelinePublicExtended(PipelinePublic):
    asset: Asset | None

# Properties to receive on pipeline creation
class PipelineCreate(PipelineBase):
    title: str = Field(min_length=1, max_length=255)

class PipelinesPublic(SQLModel):
    data: list[PipelinePublic]
    count: int

class PipelineUpdate(SQLModel):
    data: Optional[dict] = Field(nullable=True, sa_type=JSONB)

class PipelinesActionTypes(str, Enum):
    run = "run"
    cancel = "cancel"
