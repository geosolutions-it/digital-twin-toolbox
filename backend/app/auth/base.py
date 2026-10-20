from abc import ABC, abstractmethod

from fastapi import Request
from sqlmodel import Session

from app.models.user import User


class AuthProvider(ABC):
    """Pluggable identity seam: resolves a request to the acting User."""

    name: str  # value of settings.AUTH_PROVIDER that selects this provider

    @abstractmethod
    def get_current_user(self, session: Session, request: Request) -> User:
        raise NotImplementedError
