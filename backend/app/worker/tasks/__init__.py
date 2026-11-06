CAPABILITIES = {
    'vector': {
        'extensions': {
            '.shp.zip': 'inspect_vector',
            '.tiff': 'inspect_raster',
            '.tif': 'inspect_raster',
        },
    },
    'point-cloud': {
        'extensions': {
            '.laz': 'inspect_pointcloud',
            '.las': 'inspect_pointcloud',
        },
    },
    'mesh': {
        'extensions': {
            '.obj': 'inspect_mesh',
            '.obj.zip': 'inspect_mesh',
        },
    },
    'common': {
        'extensions': {
            '.glb': 'inspect_glb',
        },
    },
}

TASK_QUEUES = {
    'inspect_vector': 'vector',
    'inspect_pointcloud': 'point-cloud',
    'inspect_raster': 'vector',
    'inspect_glb': 'common',
    'inspect_mesh': 'mesh',
    'create_polygon_3dtiles': 'vector',
    'create_terrain_tiles': 'vector',
    'read_vector_fields': 'vector',
    'read_vector_sample': 'vector',
    'create_point_instance_3dtiles': 'vector',
    'create_point_cloud_3dtiles': 'point-cloud',
    'denoise_point_cloud': 'point-cloud',
    'create_mesh_3dtiles': 'mesh',
    'read_mesh_bbox': 'mesh',
    'complete_asset_remove_process': 'common',
    'complete_pipeline_remove_process': 'common',
    'finalize_tileset_batch': 'common',
}


def inspection_task_for_extension(extension: str) -> str | None:
    for caps in CAPABILITIES.values():
        task = caps.get('extensions', {}).get(extension)
        if task:
            return task
    return None
