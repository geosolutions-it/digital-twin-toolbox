import os
from osgeo import gdal
from pyproj import CRS
from app.core.config import settings

ogr2ogr_db = f"dbname='{settings.POSTGRES_TASKS_DB}' host='{settings.POSTGRES_SERVER}' port='{settings.POSTGRES_PORT}' user='{settings.POSTGRES_USER}' password='{settings.POSTGRES_PASSWORD}'"


def identify_projection(projection):
    try:
        return CRS(projection).to_epsg()
    except Exception:
        return None


def import_vector_to_postgres(asset_upload_path, table_name, geometry_column_name, fid_column_name, epsg, to_ellipsoidal_height):
    lco = [
        f'GEOMETRY_NAME={geometry_column_name}',
        f'FID={fid_column_name}',
        'SPATIAL_INDEX=GIST',
    ]

    kwargs = dict(
        format='PostgreSQL',
        dstSRS='EPSG:4326',
        layerName=table_name,
        layerCreationOptions=lco,
        dim='XYZ',
    )

    if to_ellipsoidal_height:
        kwargs['srcSRS'] = f'EPSG:{epsg}+3855'
        kwargs['dstSRS'] = 'EPSG:4326+4979'

    gdal.VectorTranslate(
        f'PG:{ogr2ogr_db}',
        asset_upload_path,
        options=gdal.VectorTranslateOptions(**kwargs)
    )


def export_geojson_from_postgres(output_path, table_name, limit):
    sql = f'SELECT * FROM "{table_name}"'
    if limit is not None:
        sql += f' LIMIT {round(limit)}'

    gdal.VectorTranslate(
        output_path,
        f'PG:{ogr2ogr_db}',
        options=gdal.VectorTranslateOptions(format='GeoJSON', SQLStatement=sql)
    )

    if not os.path.isfile(output_path):
        raise Exception("Sample not created")
