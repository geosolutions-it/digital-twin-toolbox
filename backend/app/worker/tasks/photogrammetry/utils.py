import logging
import subprocess
import os
import sys
import json
import psutil
import cv2
from app.worker.common.utils import run_subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_OpenSfM_bin():
    """Returns the command to run OpenSfM binaries"""
    return ['/bin/micromamba', 'run', '-n', 'opensfm', '/source/OpenSfM/bin/opensfm']

# OpenSfM presets per survey type, auto-selected by OPK detection. Resource keys are injected
# at runtime; 'reconstruct_algorithm' (CLI flag) and 'depthmap_min_consistent_views' (dense
# stage) are not config.yaml keys.
SFM_PRESET_AERIAL = {
    'reconstruct_algorithm': 'triangulation',
    'feature_type': 'SIFT',
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
    'undistorted_image_format': 'jpg',
    'depthmap_min_consistent_views': 3,
}

SFM_PRESET_HANDHELD = {
    'reconstruct_algorithm': 'incremental',
    'feature_type': 'SIFT',
    'feature_min_frames': 8000,
    'sift_peak_threshold': 0.066,
    'matcher_type': 'FLANN',
    'flann_algorithm': 'KDTREE',
    'matching_gps_neighbors': 0,
    'matching_gps_distance': 0,
    'matching_graph_rounds': 0,
    'triangulation_type': 'ROBUST',
    'use_exif_size': 'no',
    'use_altitude_tag': 'no',
    'optimize_camera_parameters': 'yes',
    'bundle_outlier_filtering_type': 'AUTO',
    'align_method': 'auto',
    'align_orientation_prior': 'horizontal',
    'local_bundle_radius': 0,
    'bundle_use_gcp': 'no',
    'retriangulation_ratio': 2,
    'undistorted_image_format': 'jpg',
    'depthmap_min_consistent_views': 2,
}

# config.yaml keys: everything in a preset except the non-OpenSfM helper keys.
_NON_CONFIG_KEYS = {'reconstruct_algorithm', 'depthmap_min_consistent_views'}


def survey_preset(process_dir, override=None):
    """Preset for this survey: aerial if OPK detected (or override), else handheld."""
    aerial = override if override is not None else is_aerial_survey(process_dir)
    return SFM_PRESET_AERIAL if aerial else SFM_PRESET_HANDHELD


def sfm_config_yaml(preset, resources):
    """Build the OpenSfM config.yaml dict: preset SfM keys (minus helpers) + runtime resources."""
    cfg = {k: v for k, v in preset.items() if k not in _NON_CONFIG_KEYS}
    cfg['processes'] = resources['processes']
    cfg['read_processes'] = resources['read_processes']
    cfg['feature_process_size'] = resources['feature_process_size']
    return cfg


def is_aerial_survey(process_dir):
    """Aerial if any extracted exif (process_dir/exif/*.exif) carries OPK orientation priors."""
    exif_dir = os.path.join(process_dir, 'exif')
    if not os.path.isdir(exif_dir):
        return False
    for name in os.listdir(exif_dir):
        if not name.endswith('.exif'):
            continue
        try:
            with open(os.path.join(exif_dir, name)) as f:
                meta = json.load(f)
        except (ValueError, OSError):
            continue
        if isinstance(meta, dict) and 'opk' in meta:
            return True
    return False

def build_params(process_dir, config):
    """Resolve the mesh/texture file paths under process_dir; tuning comes from config."""
    return {
        **config,
        'process_dir': process_dir,
        'output_xyz': os.path.join(process_dir, 'merged.xyz'),
        'output_ply': os.path.join(process_dir, 'mesh.ply'),
        'output_textured_dir': os.path.join(process_dir, 'textured'),
        'output_textured_dir_zip': os.path.join(process_dir, 'textured.zip'),
    }

def remove_if_exists(path):
    """Remove file if it exists"""
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

def calculate_depthmap_resources():
    """Calculate optimal resource allocation for depth map computation"""
    available_memory_mb = memory_available()
    cpu_count = get_cpu_count()
    
    depthmap_processes = max(1, min(cpu_count // 2, 4))
    depthmap_resolution = 2048  # Default resolution
    
    if available_memory_mb < 4000:
        depthmap_processes = max(1, depthmap_processes - 1)
        depthmap_resolution = 1536
    elif available_memory_mb > 16000:
        depthmap_resolution = 3072
    
    depthmap_resolution = (depthmap_resolution // 16) * 16
    
    logger.info(f"Depthmap resource allocation: {depthmap_processes} processes, {depthmap_resolution}px resolution")
    
    return {
        "depthmap_processes": depthmap_processes,
        "depthmap_resolution": depthmap_resolution
    }

def create_config_for_stage(process_dir: str, config_yaml: dict):
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

def run_step(step_name, command, process_dir: str, skip_check=False):
    """Run a processing step if it hasn't been completed already"""
    
    if not skip_check:
        completed_steps = get_completed_steps(process_dir)
        
        if step_name in completed_steps:
            logger.info(f"Skipping already completed step: {step_name}")
            return True
        
    logger.info(f"Running step: {step_name}")
    try:
        run_subprocess(command, check=True)
        return True
    except Exception as e:
        logger.error(f"Step {step_name} failed: {e}")
        return False

