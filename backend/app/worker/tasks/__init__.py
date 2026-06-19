CAPABILITIES = {
    'vector': {
        'extensions': {
            '.shp.zip': 'inspect_vector',
            # Raster metadata is extracted on the vector worker because raster assets are
            # used as colorization inputs for the point cloud pipeline (PDAL filters.colorization).
            '.tiff': 'inspect_raster',
            '.tif': 'inspect_raster',
        },
        'pipeline_matchers': [
            {'geometry_type': 'Polygon'},
            {'geometry_type': 'Point'},
        ],
    },
    'point-cloud': {
        'extensions': {
            '.laz': 'inspect_pointcloud',
            '.las': 'inspect_pointcloud',
        },
        'pipeline_matchers': [
            {'geometry_type': 'PointCloud'},
        ],
    },
    'mesh': {
        'extensions': {
            '.obj': 'inspect_mesh',
            '.ply': 'inspect_mesh',
            '.obj.zip': 'inspect_mesh',
        },
        'pipeline_matchers': [
            {'asset_type': 'Mesh'},
        ],
    },
    'photogrammetry': {
        'extensions': {
            '.phg.zip': 'inspect_photogrammetry',
        },
        'pipeline_matchers': [
            {'asset_type': 'Photogrammetry'},
        ],
    },
    # Shared queue drained by every worker: lightweight, dependency-free tasks
    # (GLB inspection + asset/pipeline cleanup) that must run regardless of which
    # component workers are deployed. GLB lives here (not under 'mesh') so it can be
    # imported without the heavy mesh worker.
    'common': {
        'extensions': {
            '.glb': 'inspect_glb',
        },
        'pipeline_matchers': [],
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


def pipeline_queue_for_asset(asset_type: str | None, geometry_type: str | None) -> str | None:
    for queue, caps in CAPABILITIES.items():
        for matcher in caps.get('pipeline_matchers', []):
            expected_asset_type = matcher.get('asset_type')
            expected_geometry_type = matcher.get('geometry_type')
            if expected_asset_type is not None and expected_asset_type != asset_type:
                continue
            if expected_geometry_type is not None and expected_geometry_type != geometry_type:
                continue
            return queue
    return None
