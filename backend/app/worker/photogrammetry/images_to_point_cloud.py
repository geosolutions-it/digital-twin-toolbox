
import logging
import subprocess
import os
import json
import time
import shutil
import sys
import psutil
import cv2

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
    

    #TODO: Adjust these values based on benchmarking  specific workload
    # memory_per_process_mb = 2000 + (20 * max_mp) 
    # print(f"Memory per process: {memory_per_process_mb}MB")
    # memory_limited_processes = max(1, int(available_memory_mb / memory_per_process_mb))
    # logger.info(f"Memory-limited processes: {memory_limited_processes}")
    
    processes = max(1, cpu_count)
    logger.info(f"Calculated processes: {processes}")
    depthmap_resolution = 2048  
    feature_process_size = 2048
    if processes > 16 and available_memory_mb > 16000:
        depthmap_resolution = max(4096, max(max_width, max_height))
        feature_process_size = 4096
    elif processes > 8 and available_memory_mb > 8000:
        depthmap_resolution = max(2048, max(max_width, max_height)/2)
        feature_process_size = 2048
    else:
        depthmap_resolution = max(1024, max(max_width, max_height)/4)

    
    depthmap_processes = max(1, int(processes / 2))  


    return {
        "processes": processes,
        "read_processes": processes,
        "depthmap_resolution": depthmap_resolution,
        "depthmap_processes": depthmap_processes,
        "feature_process_size": feature_process_size,
        "memory_mb": available_memory_mb
    }

def update_config_for_stage(process_dir: str, config_updates):
    """Update the config.yaml file for a specific pipeline stage"""
    config_path = os.path.join(process_dir, 'config.yaml')
    
    with open(config_path, 'r') as f:
        config_lines = f.readlines()
    
    config_dict = {}
    for line in config_lines:
        if ':' in line:
            key, value = line.split(':', 1)
            config_dict[key.strip()] = value.strip()
    
    config_dict.update(config_updates)
    
    config_list = [f"{key}: {value}" for key, value in config_dict.items()]
    with open(config_path, 'w') as f:
        f.write('\n'.join(config_list))
    
    logger.info(f"Updated configuration for next stage: {config_updates}")

def run(process_dir, config):
    start = time.time()
    logger.info("Start OpenSfM process")

    for f in os.listdir(process_dir):
        if f != 'images':
            f_path = os.path.join(process_dir, f)
            if os.path.isfile(f_path):
                os.remove(f_path)
            else:
                shutil.rmtree(f_path)

    images_dir = os.path.join(process_dir, 'images')
    resources = calculate_resource_allocation(images_dir)
    
    logger.info(f"Resource allocation: {resources['processes']} processes, "
                f"{resources['feature_process_size']} feature process size")

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
        'depthmap_resolution': 4096,
        **config
    }

    config_list = []
    for key in config_yaml:
        config_list.append(f'{key}: {config_yaml[key]}')

    with open(os.path.join(process_dir, 'config.yaml'), 'w') as f:
        f.write('\n'.join(config_list))
    
    original_camera_models_overrides = os.path.join(images_dir, 'camera_models_overrides.json')
    camera_models_overrides = os.path.join(process_dir, 'camera_models_overrides.json')
    original_exif_overrides = os.path.join(images_dir, 'exif_overrides.json')
    exif_overrides = os.path.join(process_dir, 'exif_overrides.json')
    if os.path.exists(original_camera_models_overrides):
        shutil.copyfile(original_camera_models_overrides, camera_models_overrides)
    if os.path.exists(original_exif_overrides):
        shutil.copyfile(original_exif_overrides, exif_overrides)

    cmd = get_OpenSfM_bin()

    subprocess.run(cmd + ['extract_metadata', process_dir],check=True)
    remove_if_exists(camera_models_overrides)
    remove_if_exists(exif_overrides)
    subprocess.run(cmd + ['detect_features', process_dir],check=True)
    subprocess.run(cmd + ['match_features', process_dir],check=True)
    subprocess.run(cmd + ['create_tracks', process_dir],check=True)
    subprocess.run(cmd + ['reconstruct', '--algorithm', 'triangulation', process_dir])

    subprocess.run(cmd + ['compute_statistics', process_dir])
    subprocess.run(cmd + ['export_report', process_dir])

    subprocess.run(cmd + ['export_ply', process_dir])

    reconstruction = None
    with open(os.path.join(process_dir, 'reconstruction.json'), 'r') as f:
        reconstruction = json.load(f)

    cameras_path = os.path.join(process_dir, 'camera_models.json')
    remove_if_exists(cameras_path)

    cameras = reconstruction[0].get('cameras')
    with open(cameras_path, 'w') as f:
        json.dump(cameras, f, indent=4)

    update_config_for_stage(process_dir, {
        'processes': resources['depthmap_processes'],
        'read_processes': resources['depthmap_processes'],
        'depthmap_resolution': resources['depthmap_resolution'],
    })
    subprocess.run(cmd + ['undistort', process_dir])
    subprocess.run(cmd + ['compute_depthmaps', process_dir])
    subprocess.run(cmd + ['export_visualsfm', process_dir])

    end = time.time()
    elapsed_time = end - start
    logger.info(f"End of OpenSfM process in {elapsed_time} seconds")
