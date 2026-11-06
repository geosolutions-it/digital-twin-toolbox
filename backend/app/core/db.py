from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.models.user import User

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    if session.exec(select(User)).first() is None:
        session.add(User())
        session.commit()
