from sqlmodel import Session, create_engine, select

from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    # make sure all SQLModel models are imported (app.models) before initializing DB
    # otherwise, SQLModel might fail to initialize relationships properly
    # for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28
    from app import crud
    from app.models.user import User, UserCreate

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
