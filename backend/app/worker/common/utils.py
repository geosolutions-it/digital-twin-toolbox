import os
import shutil
from app.core.config import settings


def get_asset_upload_path(pathname):
    return os.path.join(settings.ASSETS_DATA, "upload", pathname)


def get_asset_table_name(asset_id):
    id = f"{asset_id}".replace('-', '_')
    return f'asset_{id}'


def get_pipeline_table_name(pipeline_id):
    id = f"{pipeline_id}".replace('-', '_')
    return f'pipeline_{id}'


def setup_output_directory(pipeline_id):
    relative_output_path = os.path.join("output", f"{pipeline_id}")
    output_path = os.path.join(settings.ASSETS_DATA, relative_output_path)

    try:
        for filename in os.listdir(output_path):
            if filename != 'process':
                shutil.rmtree(os.path.join(output_path, filename))
    except Exception:
        pass

    os.makedirs(output_path, exist_ok=True)

    return {
        'relative_output_path': relative_output_path,
        'output_path': output_path,
        'output_path_3dtiles': os.path.join(output_path, 'tiles'),
        'output_path_3dtiles_zip': os.path.join(output_path, 'download'),
        'output_tileset': os.path.join(settings.API_V1_STR, relative_output_path, 'tiles', 'tileset.json'),
        'output_tileset_zip': os.path.join(settings.API_V1_STR, relative_output_path, 'download.zip'),
    }
