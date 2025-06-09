import os
from app.core.config import settings

# def get_asset_upload_path(asset_id, extension, name = 'index'):
#     return os.path.join(settings.ASSETS_DATA, "upload", f"{asset_id}", f"{asset_id}/{name}{extension}")

def get_asset_upload_path(pathname):
    return os.path.join(settings.ASSETS_DATA, "upload", f"{pathname}")

def get_asset_table_name(asset_id):
    a_id = f"{asset_id}".replace('-', '_')
    table_name = f'asset_{a_id}'
    return table_name

def get_pipeline_table_name(pipeline_id):
    p_id = f"{pipeline_id}".replace('-', '_')
    table_name = f'pipeline_{p_id}'
    return table_name
