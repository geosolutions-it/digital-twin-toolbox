import uuid

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Identity columns are added by the auth provider that needs them."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
