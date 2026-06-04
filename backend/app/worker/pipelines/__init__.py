from app.worker.main import celery
from app.worker.pipelines import polygon, point, pointcloud, obj, photogrammetry


def run(pipeline_extended):
    asset = pipeline_extended['asset']
    geometry_type = asset.get('geometry_type')
    asset_type = asset.get('asset_type')

    if asset_type == 'Mesh':
        return obj.run(pipeline_extended)
    if geometry_type == 'Polygon':
        return polygon.run(pipeline_extended)
    if geometry_type == 'Point':
        return point.run(pipeline_extended)
    if geometry_type == 'PointCloud':
        return pointcloud.run(pipeline_extended)
    if asset_type == 'Photogrammetry':
        return photogrammetry.run(pipeline_extended)
    raise ValueError(f"No pipeline for asset_type={asset_type!r}, geometry_type={geometry_type!r}")


_EXTENSION_TO_INSPECTION_TASK = {
    '.shp.zip': 'inspect_vector',
    '.laz': 'inspect_pointcloud',
    '.las': 'inspect_pointcloud',
    '.tiff': 'inspect_raster',
    '.tif': 'inspect_raster',
    '.phg.zip': 'inspect_photogrammetry',
    '.glb': 'inspect_glb',
    '.obj': 'inspect_mesh',
    '.ply': 'inspect_mesh',
}


def dispatch_upload_inspection(options):
    extension = options['asset']['extension']
    task_name = _EXTENSION_TO_INSPECTION_TASK.get(extension)
    if not task_name:
        raise ValueError(f"No inspection task for extension {extension!r}")
    return celery.send_task(task_name, kwargs={'options': options})
