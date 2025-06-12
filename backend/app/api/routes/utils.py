from fastapi import APIRouter, Depends, HTTPException
from pydantic.networks import EmailStr
from sqlmodel import select

from typing import Any
from app.api.deps import get_current_active_superuser, CurrentUser, SessionDep
from app.models import Message, Pipeline, Asset
from app.utils import generate_test_email, send_email
from celery.states import SUCCESS
from app.core.config import settings
import shutil
import os
from pathlib import Path
from app.worker.utils import get_asset_upload_path
from app.worker.main import complete_upload_process
import zipfile

router = APIRouter()


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")

@router.get("/map", response_model=None)
async def create_map_config(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    MapStore map configuration
    """
    layers = [
        {
            'format': 'image/jpeg',
            'group': 'background',
            'name': 'osm:osm_simple_light',
            'opacity': 1,
            'title': 'OSM Simple Light',
            'thumbURL': 'assets/img/osm-simple-light.jpg',
            'type': 'wms',
            'url': [
                'https://maps1.geosolutionsgroup.com/geoserver/wms',
                'https://maps2.geosolutionsgroup.com/geoserver/wms',
                'https://maps3.geosolutionsgroup.com/geoserver/wms',
                'https://maps4.geosolutionsgroup.com/geoserver/wms',
                'https://maps5.geosolutionsgroup.com/geoserver/wms',
                'https://maps6.geosolutionsgroup.com/geoserver/wms'
            ],
            'tileSize': 512,
            'visibility': False,
            'singleTile': False,
            'credits': {
                'title': 'OSM Simple Light | Rendering <a href=\'https://www.geo-solutions.it/\'>GeoSolutions</a> | Data © <a href=\'http://www.openstreetmap.org/\'>OpenStreetMap</a> contributors, <a href=\'http://www.openstreetmap.org/copyright\'>ODbL</a>'
            }
        },
        {
            'format': 'image/jpeg',
            'group': 'background',
            'name': 'osm:osm_simple_dark',
            'opacity': 1,
            'title': 'OSM Simple Dark',
            'thumbURL': 'assets/img/osm-simple-dark.jpg',
            'type': 'wms',
            'url': [
                'https://maps6.geosolutionsgroup.com/geoserver/wms',
                'https://maps3.geosolutionsgroup.com/geoserver/wms',
                'https://maps1.geosolutionsgroup.com/geoserver/wms',
                'https://maps4.geosolutionsgroup.com/geoserver/wms',
                'https://maps2.geosolutionsgroup.com/geoserver/wms',
                'https://maps5.geosolutionsgroup.com/geoserver/wms'
            ],
            'tileSize': 512,
            'visibility': False,
            'singleTile': False,
            'credits': {
                'title': 'OSM Simple Dark | Rendering <a href=\'https://www.geo-solutions.it/\'>GeoSolutions</a> | Data © <a href=\'http://www.openstreetmap.org/\'>OpenStreetMap</a> contributors, <a href=\'http://www.openstreetmap.org/copyright\'>ODbL</a>'
            }
        },
        {
            'format': 'image/jpeg',
            'group': 'background',
            'name': 'osm:osm',
            'opacity': 1,
            'title': 'OSM Bright',
            'thumbURL': 'assets/img/osm-bright.jpg',
            'type': 'wms',
            'url': [
                'https://maps1.geosolutionsgroup.com/geoserver/wms',
                'https://maps2.geosolutionsgroup.com/geoserver/wms',
                'https://maps3.geosolutionsgroup.com/geoserver/wms',
                'https://maps4.geosolutionsgroup.com/geoserver/wms',
                'https://maps5.geosolutionsgroup.com/geoserver/wms',
                'https://maps6.geosolutionsgroup.com/geoserver/wms'
            ],
            'tileSize': 512,
            'visibility': True,
            'singleTile': False,
            'credits': {
                'title': 'OSM Bright | Rendering <a href=\'https://www.geo-solutions.it/\'>GeoSolutions</a> | Data © <a href=\'http://www.openstreetmap.org/\'>OpenStreetMap</a> contributors, <a href=\'http://www.openstreetmap.org/copyright\'>ODbL</a>'
            }
        },
        {
            'format': 'image/jpeg',
            'group': 'background',
            'name': 's2cloudless:s2cloudless',
            'opacity': 1,
            'title': 'Sentinel 2 Cloudless',
            'type': 'wms',
            'url': [
                'https://maps1.geosolutionsgroup.com/geoserver/wms',
                'https://maps2.geosolutionsgroup.com/geoserver/wms',
                'https://maps3.geosolutionsgroup.com/geoserver/wms',
                'https://maps4.geosolutionsgroup.com/geoserver/wms',
                'https://maps5.geosolutionsgroup.com/geoserver/wms',
                'https://maps6.geosolutionsgroup.com/geoserver/wms'
            ],
            'tileSize': 512,
            'source': 's2cloudless',
            'singleTile': False,
            'visibility': False
        },
        {
            'type': 'osm',
            'title': 'Open Street Map',
            'name': 'mapnik',
            'source': 'osm',
            'group': 'background',
            'visibility': False
        },
        {
            'source': 'ol',
            'group': 'background',
            'title': 'Empty Background',
            'fixed': True,
            'type': 'empty',
            'visibility': False
        }
    ]
    pipelines = []
    if current_user.is_superuser:
        statement = select(Pipeline).where(Pipeline.task_status == SUCCESS)
        pipelines = session.exec(statement.order_by(Pipeline.title.asc())).all()
    else:
        statement = (
            select(Pipeline)
            .where(Pipeline.owner_id == current_user.id)
            .where(Pipeline.task_status == SUCCESS)
        )
        pipelines = session.exec(statement.order_by(Pipeline.title.asc())).all()

    catalog_services = {}
    for pipeline in pipelines:
        if pipeline.task_result and 'tileset' in pipeline.task_result:
            catalog_services[pipeline.id] = {
                'url': f"{settings.server_host}{pipeline.task_result['tileset']}",
                'type': '3dtiles',
                'title': pipeline.title,
                'autoload': False
            }

    return {
        'version': 2,
        'map': {
            'projection': 'EPSG:900913',
            'units': 'm',
            'visualizationMode': '3D',
            'center': {
                'x': 0,
                'y': 0,
                'crs': 'EPSG:4326'
            },
            'zoom': 5,
            'maxExtent': [
                -20037508.34,
                -20037508.34,
                20037508.34,
                20037508.34
            ],
            'layers': layers
        },
        'catalogServices': {
            'services': catalog_services
        }
    }

def create_asset(session, file_info, current_user, to_ellipsoidal_height):

    filename = file_info.get('filename')
    content_type = file_info.get('content_type')
    content_size = file_info.get('content_size')
    file = file_info.get('file')

    extension = "".join(Path(filename).suffixes)

    if extension == '.zip':
        zip_file = file
        archive = zipfile.ZipFile(zip_file, 'r')
        with archive as z:
            zip_filenames = z.namelist()
            if len(zip_filenames) == 0:
                raise HTTPException(status_code=500, detail=f"Not supported file, empty zip file")
            zip_file_extensions = []
            for zip_filename in zip_filenames:
                zip_file_extension = "".join(Path(zip_filename).suffixes).lower()
                zip_file_extensions.append(zip_file_extension)
            if '.shp' in zip_file_extensions:
                filename = filename.replace('.zip', '.shp.zip')
                extension = "".join(Path(filename).suffixes)
            else:
                if not all(ext in ['.jpg', '.json'] for ext in zip_file_extensions):
                    raise HTTPException(status_code=500, detail=f"Not supported file, empty zip file")
                else:
                    filename = filename.replace('.zip', '.phg.zip')
                    extension = "".join(Path(filename).suffixes)


    check_statement = select(Asset).where(Asset.owner_id == current_user.id).where(Asset.filename == filename).limit(1)
    results = session.exec(check_statement)
    check_asset = results.first()

    if check_asset:
        raise HTTPException(status_code=400, detail="Asset with this filename already exists")

    vector_data_extensions = [".shp.zip"]
    point_cloud_data_extensions = [".laz", ".las"]
    raster_formats = [".tiff", ".tif"]
    photogrammetry_formats = [".phg.zip"]
    supported_extensions = [".glb"] + vector_data_extensions + point_cloud_data_extensions + raster_formats + photogrammetry_formats

    if not extension in supported_extensions:
        supported_extensions_list = ", ".join(supported_extensions)
        raise HTTPException(status_code=500, detail=f"Not supported file, supported extensions {supported_extensions_list}")

    asset_in = {
        'filename': filename,
        'content_type': content_type,
        'content_size': content_size,
        'extension': extension,
        'upload_result': {}
    }

    asset = Asset.model_validate(asset_in, update={"owner_id": current_user.id})

    output_file_path = get_asset_upload_path(f"{asset.id}/index{asset.extension}")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    if isinstance(file, str):
        shutil.move(file, output_file_path)
    else:
        try:
            file.seek(0)
            with open(output_file_path, 'wb') as f:
                while contents := file.read(1024 * 1024):
                    f.write(contents)
        except Exception:
            raise HTTPException(status_code=500, detail="There was an error uploading the file")
        finally:
            file.close()

    session.add(asset)
    session.commit()
    session.refresh(asset)

    task = complete_upload_process.delay(options={
        'asset': asset.model_dump(),
        'vector_data_extensions': vector_data_extensions,
        'point_cloud_data_extensions': point_cloud_data_extensions,
        'raster_formats': raster_formats,
        'photogrammetry_formats': photogrammetry_formats,
        'to_ellipsoidal_height': to_ellipsoidal_height
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
