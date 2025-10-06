import logging
import os
import json
import time
import numpy as np
import open3d as o3d
import app.worker.photogrammetry.mask_images as mask_images
from app.worker.photogrammetry.point_cloud_to_mesh import transform_extent_to_local
from app.worker.photogrammetry.utils import (
    get_OpenSfM_bin, run_step, create_config_for_stage,
    calculate_depthmap_resources
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def crop_dense_point_cloud(params):
    """Crop a dense point cloud using geographic bounds"""
    process_dir = params.get('process_dir')

    reference_lla = None
    reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
    with open(reference_lla_path, 'r') as f:
        reference_lla = json.load(f)

    config = None
    config_path = os.path.join(process_dir, 'images', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)

    bbox = transform_extent_to_local(reference_lla, config)

    if bbox:
        logger.info("Cropping dense point cloud")
        dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged.ply')
        pcd = o3d.io.read_point_cloud(dense_ply)
        min_bound = np.array([bbox[0], bbox[1], float('-inf')])
        max_bound = np.array([bbox[2], bbox[3], float('inf')])
        bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound=min_bound, max_bound=max_bound)
        cropped_pcd = pcd.crop(bbox)
        o3d.io.write_point_cloud(dense_ply, cropped_pcd, write_ascii=True, compressed=False, print_progress=True)
    else:
        logger.info("Skip point cloud cropping")

def run(process_dir, config):
    start = time.time()
    logger.info("Start dense point cloud reconstruction process")

    auto_resolutions_computation = config.get('auto_resolutions_computation', True)
    
    reconstruction_path = os.path.join(process_dir, 'reconstruction.json')
    if not os.path.exists(reconstruction_path):
        logger.error("Sparse reconstruction not found. Run images_to_sparse_reconstruction first.")
        return False
    
    mask_images.run(process_dir)

    depthmap_resolution = config.get("depthmap_resolution", 1024)
    depthmap_processes = config.get("depthmap_processes", 1)

    if auto_resolutions_computation:
        resources = calculate_depthmap_resources()
        depthmap_processes = resources["depthmap_processes"]
        depthmap_resolution = resources["depthmap_resolution"]
    
    config_yaml = {
        'processes': depthmap_processes,
        'read_processes': depthmap_processes,
        'depthmap_min_consistent_views': 3,
        'depthmap_resolution': depthmap_resolution,
        'undistorted_image_format': 'jpg',
        'undistorted_image_max_size': depthmap_resolution
    }
    
    create_config_for_stage(process_dir, config_yaml)
    
    cmd = get_OpenSfM_bin()
    

    run_step('undistort', cmd + ['undistort', process_dir], process_dir)
    run_step('compute_depthmaps', cmd + ['compute_depthmaps', process_dir], process_dir)
    
    crop_dense_point_cloud({'process_dir': process_dir})
    
    end = time.time()
    elapsed_time = end - start
    logger.info(f"End of dense point cloud reconstruction process in {elapsed_time} seconds")
    return True