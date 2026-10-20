from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(session: SessionDep) -> User:
    # Single implicit principal: the seeded FIRST_SUPERUSER. The app has no in-app
    # auth; identity, when needed, is an external concern (see PLUGGABLE_AUTH_PLAN.md).
    return session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()


CurrentUser = Annotated[User, Depends(get_current_user)]
