CAPABILITIES = {
    'vector': {
        'extensions': {
            '.shp.zip': 'inspect_vector',
            # Raster metadata is extracted on the vector worker because raster assets are
            # used as colorization inputs for the point cloud pipeline (PDAL filters.colorization).
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
    'photogrammetry': {
        'extensions': {
            '.phg.zip': 'inspect_photogrammetry',
        },
    },
    # Shared queue drained by every worker: lightweight, dependency-free tasks
    # (GLB inspection + asset/pipeline cleanup) that must run regardless of which
    # component workers are deployed. GLB lives here (not under 'mesh') so it can be
    # imported without the heavy mesh worker.
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
    'inspect_photogrammetry': 'photogrammetry',
    'inspect_glb': 'common',
    'inspect_mesh': 'mesh',
    'create_polygon_3dtiles': 'vector',
    'create_point_instance_3dtiles': 'vector',
    'create_point_cloud_3dtiles': 'point-cloud',
    'create_obj_mesh_3dtiles': 'mesh',
    'create_photogrammetry_3dtiles': 'photogrammetry',
    'complete_asset_remove_process': 'common',
    'complete_pipeline_remove_process': 'common',
}


def inspection_task_for_extension(extension: str) -> str | None:
    for caps in CAPABILITIES.values():
        task = caps.get('extensions', {}).get(extension)
        if task:
            return task
    return None
