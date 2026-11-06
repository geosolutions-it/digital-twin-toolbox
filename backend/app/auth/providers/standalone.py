from fastapi import Request
from sqlmodel import Session, select

from app.auth.base import AuthProvider
from app.models.user import User


class StandaloneAuthProvider(AuthProvider):
    """No in-app auth: every request acts as the single implicit user."""

    name = "standalone"

    def get_current_user(self, session: Session, request: Request) -> User:
        return session.exec(select(User)).first()
