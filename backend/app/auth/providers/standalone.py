from fastapi import Request
from sqlmodel import Session, select

from app.auth.base import AuthProvider
from app.core.config import settings
from app.models.user import User


class StandaloneAuthProvider(AuthProvider):
    """No in-app auth: every request acts as the seeded implicit superuser."""

    name = "standalone"

    def get_current_user(self, session: Session, request: Request) -> User:
        return session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
