
import logging
import subprocess
import os
import json
import time
import shutil
import sys
import psutil
import cv2 
import math
import numpy as np
from PIL import Image
from app.worker.photogrammetry.point_cloud_to_mesh import transform_extent_to_local
import open3d as o3d

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_OpenSfM_bin():
    return ['micromamba', 'run', '-n', 'opensfm', '/source/OpenSfM/bin/opensfm']

def remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)

def memory_available() -> int:
    """Returns available memory in MB"""
    if sys.platform == "win32":
        # Windows implementation
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
            def __init__(self) -> None:
                self.dwLength = ctypes.sizeof(self)
                super(MEMORYSTATUSEX, self).__init__()
        
        stat = MEMORYSTATUSEX()
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return int(stat.ullAvailPhys / 1024 / 1024)
    else:
        # Linux/macOS implementation
        with os.popen("free -t -m") as fp:
            lines = fp.readlines()
        if not lines:
            return int(psutil.virtual_memory().available / 1024 / 1024)
        available_mem = int(lines[1].split()[6])
        return available_mem

def get_cpu_count() -> int:
    """Returns the number of available CPU cores"""
    return psutil.cpu_count(logical=False) or 1  

def get_max_image_resolution(images_dir: str):
    """Get the maximum resolution of images in the directory"""
    max_width, max_height = 0, 0
    try:
        for filename in os.listdir(images_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')):
                img_path = os.path.join(images_dir, filename)
                img = cv2.imread(img_path)
                if img is not None:
                    height, width = img.shape[:2]
                    max_width = max(max_width, width)
                    max_height = max(max_height, height)
    except Exception as e:
        logger.warning(f"Error reading image dimensions: {e}")
        return (1920, 1080)
    
    if max_width == 0 or max_height == 0:
        return (1920, 1080)
    
    return (max_width, max_height)

def calculate_resource_allocation(images_dir: str):
    """Calculate optimal resource allocation based on system capabilities and image resolution"""
    available_memory_mb = memory_available()
    cpu_count = get_cpu_count()
    max_width, max_height = get_max_image_resolution(images_dir)
    max_mp = (max_width * max_height) / 1_000_000  # Megapixels
    
    logger.info(f"System has {cpu_count} CPU cores and {available_memory_mb}MB available memory")
    logger.info(f"Maximum image resolution: {max_width}x{max_height} ({max_mp:.2f}MP)")

    processes = max(1, min(cpu_count - 1, 8)) 
    depthmap_processes = max(1, processes // 2)  
    
    smallest_dimension = min(max_width, max_height)
    
    if max_mp > 20:       # Very large images
        scale_factor = 0.4
    elif max_mp > 10:     # Large images
        scale_factor = 0.6
    else:                 # Medium/small images
        scale_factor = 0.8
    
    if available_memory_mb < 4000:
        scale_factor *= 0.7
    
    feature_process_size = int(smallest_dimension * scale_factor)
    feature_process_size = max(1024, min(smallest_dimension, min(4096, feature_process_size)))
    feature_process_size = (feature_process_size // 16) * 16  
    
    depthmap_resolution = min(smallest_dimension, max(1024, int(feature_process_size * 1.2)))
    depthmap_resolution = (depthmap_resolution // 16) * 16  
    
    logger.info(f"Allocated resources: {processes} processes ({depthmap_processes} for depth maps)")
    logger.info(f"Feature process size: {feature_process_size}px (original image: {max_width}x{max_height})")
    logger.info(f"Depth map resolution: {depthmap_resolution}px (original image: {max_width}x{max_height})")
    
    return {
        "processes": processes,
        "read_processes": processes,
        "depthmap_resolution": depthmap_resolution,
        "depthmap_processes": depthmap_processes,
        "feature_process_size": feature_process_size,
        "memory_mb": available_memory_mb
    }

def create_config_for_stage(process_dir: str, config_yaml:dict):
    """Update the config.yaml file for a specific pipeline stage"""
    config_path = os.path.join(process_dir, 'config.yaml')
    
    if os.path.exists(config_path):
        os.remove(config_path)

    config_updates = []
    for key, value in config_yaml.items():
        config_updates.append(f'{key}: {value}')
    with open(config_path, 'w') as f:
        f.write('\n'.join(config_updates))
    
    logger.info(f"Updated configuration for next stage: {config_updates}")



def get_completed_steps(process_dir: str):
    """Read OpenSfM's profile.log to determine completed steps"""
    profile_log_path = os.path.join(process_dir, 'profile.log')
    completed_steps = {}
    
    if os.path.exists(profile_log_path):
        try:
            with open(profile_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and ': ' in line:
                        step, _ = line.split(': ', 1)
                        completed_steps[step] = True
            logger.info(f"Found completed steps in profile.log: {list(completed_steps.keys())}")
        except Exception as e:
            logger.warning(f"Error reading profile.log: {e}")
    
    return completed_steps

def run_step(step_name, command, process_dir: str):
    completed_steps = get_completed_steps(process_dir)
    
    if step_name in completed_steps:
        logger.info(f"Skipping already completed step: {step_name}")
        return True
        
    logger.info(f"Running step: {step_name}")
    try:
        subprocess.run(command, check=True)
        return True
    except Exception as e:
        logger.error(f"Step {step_name} failed: {e}")
        return False

def run(process_dir, config):
    start = time.time()
    logger.info("Start OpenSfM process")
    force_delete = config.get('force_delete', False)
    auto_resolutions_computation = config.get('auto_resolutions_computation', True)

    print(force_delete, 'force_delete')
    print(auto_resolutions_computation, 'auto_resolutions_computation')

    if  force_delete:
        logger.info("Starting fresh run - cleaning directory")
        for f in os.listdir(process_dir):
            if f != 'images':
                f_path = os.path.join(process_dir, f)
                if os.path.isfile(f_path):
                    os.remove(f_path)
                elif os.path.isdir(f_path):
                    shutil.rmtree(f_path)
    else:
        logger.info("Resuming from previous run based on profile.log")
    

    images_dir = os.path.join(process_dir, 'images')
    print(images_dir,'images_dir')

    resources = {
        "processes": 8,
        "read_processes": 8,
        "depthmap_resolution": config.get('depthmap_resolution'),
        "depthmap_processes": 4,
        "feature_process_size": config.get('feature_process_size'),
        "memory_mb": memory_available()
    }

    if auto_resolutions_computation:
        resources = calculate_resource_allocation(images_dir)
    
    logger.info(f"Resource allocation: {resources['processes']} processes, "
                f"{resources['feature_process_size']} feature process size, "
                f"{resources['depthmap_resolution']} depthmap resolution")

    config_yaml = {
        'processes': resources['processes'],
        'read_processes': resources['read_processes'],
        'feature_type': 'SIFT',
        'feature_process_size': resources['feature_process_size'],
        'feature_min_frames': 30000,
        'sift_peak_threshold': 0.066,
        'matcher_type': 'FLANN',
        'flann_algorithm': 'KDTREE',
        'matching_gps_neighbors': 0,
        'matching_gps_distance': 0,
        'matching_graph_rounds': 50,
        'triangulation_type': 'ROBUST',
        'use_exif_size': 'no',
        'use_altitude_tag': 'yes',
        'optimize_camera_parameters': 'yes',
        'bundle_outlier_filtering_type': 'AUTO',
        'align_method': 'auto',
        'align_orientation_prior': 'vertical',
        'local_bundle_radius': 0,
        'bundle_use_gcp': 'no',
        'retriangulation_ratio': 2,
        'undistorted_image_format': 'jpg', # tif
        'depthmap_min_consistent_views': 3,
        'depthmap_resolution': resources['depthmap_resolution']
    }

    create_config_for_stage(process_dir, config_yaml)
    
    original_camera_models_overrides = os.path.join(images_dir, 'camera_models_overrides.json')
    camera_models_overrides = os.path.join(process_dir, 'camera_models_overrides.json')
    original_exif_overrides = os.path.join(images_dir, 'exif_overrides.json')
    exif_overrides = os.path.join(process_dir, 'exif_overrides.json')
    if os.path.exists(original_camera_models_overrides):
        shutil.copyfile(original_camera_models_overrides, camera_models_overrides)
    if os.path.exists(original_exif_overrides):
        shutil.copyfile(original_exif_overrides, exif_overrides)

    cmd = get_OpenSfM_bin()

    if run_step('extract_metadata', cmd + ['extract_metadata', process_dir], process_dir):
        remove_if_exists(camera_models_overrides)
        remove_if_exists(exif_overrides)
        
    run_step('detect_features', cmd + ['detect_features', process_dir], process_dir)
    run_step('match_features', cmd + ['match_features', process_dir], process_dir)
    run_step('create_tracks', cmd + ['create_tracks', process_dir], process_dir)
    run_step('reconstruct', cmd + ['reconstruct', '--algorithm', 'triangulation', process_dir], process_dir)

    run_step('compute_statistics', cmd + ['compute_statistics', process_dir], process_dir)
    run_step('export_report', cmd + ['export_report', process_dir], process_dir)
    run_step('export_ply', cmd + ['export_ply', process_dir], process_dir)

    reconstruction = None
    reconstruction_path = os.path.join(process_dir, 'reconstruction.json')
    if os.path.exists(reconstruction_path):
        with open(reconstruction_path, 'r') as f:
            reconstruction = json.load(f)

        cameras_path = os.path.join(process_dir, 'camera_models.json')
        remove_if_exists(cameras_path)

        cameras = reconstruction[0].get('cameras')
        with open(cameras_path, 'w') as f:
            json.dump(cameras, f, indent=4)

    config_yaml.update({
        'processes': resources['depthmap_processes'],
        'read_processes': resources['depthmap_processes']
    })

    reference_lla = None
    reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
    with open(reference_lla_path, 'r') as f:
        reference_lla = json.load(f)

    config = None
    config_path = os.path.join(process_dir, 'images', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
    bbox= transform_extent_to_local(reference_lla, config)
    run_step('undistort', cmd + ['undistort', process_dir], process_dir)

    create_config_for_stage(process_dir, config_yaml)

    run_step('compute_depthmaps', cmd + ['compute_depthmaps', process_dir], process_dir)
    run_step('export_visualsfm', cmd + ['export_visualsfm', process_dir], process_dir)

    dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged.ply')
    cropped_dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged_cropped.ply')
    pcd = o3d.io.read_point_cloud(dense_ply)
    min_bound = np.array([bbox[0], bbox[1], float('-inf')])
    max_bound = np.array([bbox[2], bbox[3], float('inf')])
    bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound=min_bound, max_bound=max_bound)
    cropped_pcd = pcd.crop(bbox)
    sampled_pcd = cropped_pcd.voxel_down_sample(voxel_size=0.1)
  
    o3d.io.write_point_cloud(cropped_dense_ply, sampled_pcd , write_ascii=True, compressed=False, print_progress=True)


    original_point_count = len(cropped_pcd.points)
    target_point_count = 250000 
    if original_point_count > target_point_count:
        if original_point_count > target_point_count * 10:
            voxel_size = 0.5
            preview_pcd = cropped_pcd.voxel_down_sample(voxel_size=voxel_size)
            if len(preview_pcd.points) > target_point_count:
                sampling_ratio = target_point_count / len(preview_pcd.points)
                preview_pcd = preview_pcd.random_down_sample(sampling_ratio)
        else:
            sampling_ratio = target_point_count / original_point_count
            preview_pcd = cropped_pcd.random_down_sample(sampling_ratio)
    else:
        preview_pcd = cropped_pcd
    
    preview_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged_preview.ply')
    o3d.io.write_point_cloud(preview_ply, preview_pcd, write_ascii=True, compressed=False, print_progress=True)

    logger.info(f"Original point count: {original_point_count}")
    logger.info(f"Preview point count: {len(preview_pcd.points)}")
    logger.info(f"Reduction ratio: {len(preview_pcd.points) / original_point_count:.2f}")


    end = time.time()
    elapsed_time = end - start
    logger.info(f"End of OpenSfM process in {elapsed_time} seconds")