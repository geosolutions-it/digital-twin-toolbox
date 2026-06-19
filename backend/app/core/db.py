import psycopg

from sqlmodel import Session, create_engine, select

from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
engine_tasks = create_engine(str(settings.SQLALCHEMY_TASKS_DATABASE_URI))


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

def init_tasks_db() -> None:
    conn_args = {
        "host": settings.POSTGRES_SERVER,
        "port": settings.POSTGRES_PORT,
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD,
    }

    with psycopg.connect(**conn_args, dbname="postgres", autocommit=True) as conn:
        try:
            conn.execute(f"CREATE DATABASE {settings.POSTGRES_TASKS_DB}")
        except psycopg.errors.DuplicateDatabase:
            pass

    with psycopg.connect(**conn_args, dbname=settings.POSTGRES_TASKS_DB, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        conn.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")

    # Reconnect to update pg_setting.resetval
    # See https://github.com/postgis/docker-postgis/issues/288
    with psycopg.connect(**conn_args, dbname=settings.POSTGRES_TASKS_DB, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")
        conn.execute("CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder")
