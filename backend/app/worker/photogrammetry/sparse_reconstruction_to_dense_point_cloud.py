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
    calculate_depthmap_resources, crop_dense_point_cloud
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        'undistorted_image_max_size': int(config.get('texture_image_resolution', 4096))
    }
    
    create_config_for_stage(process_dir, config_yaml)
    
    cmd = get_OpenSfM_bin()
    

    run_step('undistort', cmd + ['undistort', process_dir], process_dir)
    run_step('compute_depthmaps', cmd + ['compute_depthmaps', process_dir], process_dir)
    run_step('export_visualsfm', cmd + ['export_visualsfm', process_dir], process_dir)
    
    crop_dense_point_cloud({'process_dir': process_dir})
    
    end = time.time()
    elapsed_time = end - start
    logger.info(f"End of dense point cloud reconstruction process in {elapsed_time} seconds")
    return True