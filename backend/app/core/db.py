from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
import subprocess

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
engine_tasks = create_engine(str(settings.SQLALCHEMY_TASKS_DATABASE_URI))

# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # from app.core.engine import engine
    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

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
    psql_connection = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}"

    subprocess.run([ 'psql', psql_connection, '-c', f'CREATE DATABASE {settings.POSTGRES_TASKS_DB};' ])
    psql_connection_db = f"{psql_connection}/{settings.POSTGRES_TASKS_DB}"
    subprocess.run([ 'psql', psql_connection_db, '-c', 'CREATE EXTENSION IF NOT EXISTS postgis;' ])
    subprocess.run([ 'psql', psql_connection_db, '-c', 'CREATE EXTENSION IF NOT EXISTS postgis_topology;' ])
    # Reconnect to update pg_setting.resetval
    # See https://github.com/postgis/docker-postgis/issues/288
    subprocess.run([ 'psql', psql_connection_db, '-c', '\c' ])
    subprocess.run([ 'psql', psql_connection_db, '-c', 'CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;' ])
    subprocess.run([ 'psql', psql_connection_db, '-c', 'CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;' ])
    return None
