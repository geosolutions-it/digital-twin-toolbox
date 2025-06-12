import os
from app.core.config import settings
from app.worker.utils import get_asset_upload_path
from uuid import UUID
from sqlmodel import Session, select
from app.models import User, Pipeline
from app.core.db import engine
from app.api.routes.utils import create_asset

def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test

def sync_uploaded_assets(create_pipeline):
    with Session(engine) as session:
        current_user = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        upload_path = get_asset_upload_path('')
        for filename in os.listdir(upload_path):
            file = os.path.join(upload_path, filename)
            if os.path.isfile(file) and not is_valid_uuid(filename):
                file_info = {
                    'filename': filename,
                    'content_type': '',
                    'content_size': 0,
                    'file': file
                }

                asset = create_asset(session=session, file_info=file_info, current_user=current_user, to_ellipsoidal_height=False)

                if create_pipeline:
                    pipeline_in = {
                        'asset_id': asset.id,
                        'title': filename,
                        'data': {},
                        'task_id': None,
                        'task_status': None,
                        'task_result': None
                    }
                    pipeline = Pipeline.model_validate(pipeline_in, update={"owner_id": current_user.id })
                    session.add(pipeline)
                    session.commit()
                    session.refresh(pipeline)

if __name__ == "__main__":

    sync_uploaded_assets(True)
