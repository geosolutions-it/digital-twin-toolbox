from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.auth import get_auth_provider
from app.core.db import engine
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(session: SessionDep, request: Request) -> User:
    # Delegates to the configured auth provider (see app/auth).
    return get_auth_provider().get_current_user(session, request)


CurrentUser = Annotated[User, Depends(get_current_user)]
