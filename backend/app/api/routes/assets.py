
from app.api.deps import CurrentUser, SessionDep
from fastapi import UploadFile, APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Any
import os
from app.models import Asset, AssetPublic, AssetsPublic, Message, Pipeline
from sqlmodel import func, select, col
from pathlib import Path
import uuid
from app.worker.utils import get_asset_upload_path
from app.worker.main import complete_upload_process, complete_asset_remove_process

router = APIRouter()

@router.get("/", response_model=AssetsPublic)
def read_assets(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100, extension: str = None, upload_status: str = None
) -> Any:
    """
    Retrieve assets.
    """
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Asset)
        if extension:
            count_statement = count_statement.where(col(Asset.extension).in_(extension.split(',')))
        count = session.exec(count_statement).one()
        statement = select(Asset).offset(skip).limit(limit)
        if extension:
            statement = statement.where(col(Asset.extension).in_(extension.split(',')))
        if upload_status:
            statement = statement.where(col(Asset.upload_status).in_(upload_status.split(',')))
        assets = session.exec(statement.order_by(Asset.filename.asc())).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Asset)
            .where(Asset.owner_id == current_user.id)
        )
        if extension:
            count_statement = count_statement.where(col(Asset.extension).in_(extension.split(',')))
        count = session.exec(count_statement).one()
        statement = (
            select(Asset)
            .where(Asset.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        if extension:
            statement = statement.where(col(Asset.extension).in_(extension.split(',')))
        if upload_status:
            statement = statement.where(col(Asset.upload_status).in_(upload_status.split(',')))
        assets = session.exec(statement.order_by(Asset.filename.asc())).all()

    return AssetsPublic(data=assets, count=count)

@router.post("/", response_model=AssetPublic)
async def create_asset(
    *, session: SessionDep, current_user: CurrentUser, file: UploadFile
) -> Any:
    """
    Create new asset.
    """

    check_statement = select(Asset).where(Asset.filename == file.filename).limit(1)
    results = session.exec(check_statement)
    check_asset = results.first()

    if check_asset:
        raise HTTPException(status_code=400, detail="Asset with this filename already exists")

    if not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="Not enough permissions")

    vector_data_extensions = [".shp.zip"]
    point_cloud_data_extensions = [".laz", ".las"]
    raster_formats = [".tiff", ".tif"]
    supported_extensions = [".glb"] + vector_data_extensions + point_cloud_data_extensions + raster_formats
    extension = "".join(Path(file.filename).suffixes)

    if not extension in supported_extensions:
        supported_extensions_list = ", ".join(supported_extensions)
        raise HTTPException(status_code=500, detail=f"Not supported file, supported extensions {supported_extensions_list}")

    asset_in = {
        'filename': file.filename,
        'content_type': file.content_type,
        'content_size': file.size,
        'extension': extension,
        'upload_result': {}
    }

    asset = Asset.model_validate(asset_in, update={"owner_id": current_user.id})
    output_file_path = get_asset_upload_path(asset.id, extension)

    try:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, 'wb') as f:
            while contents := file.file.read(1024 * 1024):
                f.write(contents)
    except Exception:
        raise HTTPException(status_code=500, detail="There was an error uploading the file")
    finally:
        file.file.close()

    session.add(asset)
    session.commit()
    session.refresh(asset)

    task = complete_upload_process.delay(options={
        'asset': asset.model_dump(),
        'vector_data_extensions': vector_data_extensions,
        'point_cloud_data_extensions': point_cloud_data_extensions,
        'raster_formats': raster_formats
    })
    asset.sqlmodel_update({
        "upload_id": task.id,
        "upload_status": task.status,
        "upload_result": task.result
    })
    session.add(asset)
    session.commit()
    session.refresh(asset)

    return asset

@router.get("/files/{filename}", response_model=None)
async def get_asset_file(session: SessionDep, current_user: CurrentUser, filename: str) -> Any:
    """
    Download asset by filename.
    """
    statement = select(Asset).where(Asset.filename == filename).limit(1)
    results = session.exec(statement)
    asset = results.first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not current_user.is_superuser and (asset.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")

    output_path = get_asset_upload_path(asset.id, asset.extension)
    return FileResponse(output_path)

@router.get("/{id}/download", response_model=None)
async def download_asset(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Download asset by id.
    """
    asset = session.get(Asset, id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not current_user.is_superuser and (asset.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")

    output_path = get_asset_upload_path(asset.id, asset.extension)
    return FileResponse(output_path)

@router.get("/{id}/sample", response_model=None)
async def read_asset_sample(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get asset sample.
    """
    asset = session.get(Asset, id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not current_user.is_superuser and (asset.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")

    if not asset.asset_type:
        raise HTTPException(status_code=500, detail="Asset does not support sample operation")

    sample_extension = '.json'
    if asset.geometry_type == 'PointCloud':
        sample_extension = '.xyz'

    sample_file_path = get_asset_upload_path(asset.id, sample_extension, 'sample')
    if not os.path.isfile(sample_file_path):
        raise HTTPException(status_code=500, detail="Sample file not available")

    return FileResponse(sample_file_path)

@router.delete("/{id}")
def delete_asset(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an asset.
    """
    asset = session.get(Asset, id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not current_user.is_superuser and (asset.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    
    statement = select(Pipeline).where(Pipeline.asset_id == asset.id)

    pipelines = session.exec(statement).all()
    for pipeline in pipelines:
        update_dict = {
            'asset_id': None
        }
        pipeline.sqlmodel_update(update_dict)
        session.add(pipeline)

    session.delete(asset)
    session.commit()

    complete_asset_remove_process.delay({
        'asset': asset.model_dump()
    })

    return Message(message="Asset deleted successfully")
