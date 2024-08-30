from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr
from sqlmodel import select

from typing import Any
from app.api.deps import get_current_active_superuser, CurrentUser, SessionDep
from app.models import Message, Pipeline
from app.utils import generate_test_email, send_email
from celery.states import SUCCESS
from app.core.config import settings

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
            'name': 'ne:ne-political',
            'opacity': 1,
            'title': 'NE Political',
            'thumbURL': 'assets/img/ne-political.jpg',
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
                'title': '<p></p>\n'
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

    for pipeline in pipelines:
        if pipeline.task_result and 'tileset' in pipeline.task_result:
            layers += [
                {
                    'id': pipeline.id,
                    'type': '3dtiles',
                    'title': pipeline.title,
                    'url': f"{settings.server_host}{pipeline.task_result['tileset']}",
                    'visibility': False
                }
            ]

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
        'toc': {
            'defaultOpen': True
        }
    }
