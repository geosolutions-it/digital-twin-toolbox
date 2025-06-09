
import logging
import subprocess
import os
import json
import time
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_OpenSfM_bin():
    return ['micromamba', 'run', '-n', 'opensfm', '/source/OpenSfM/bin/opensfm']

def remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)

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

    config_yaml = {
        'processes': 2,
        'read_processes': 2,

        'feature_type': 'SIFT',
        'feature_process_size': 7096, # 4096
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
        'depthmap_resolution': 2048,
        **config
    }

    config_list = []
    for key in config_yaml:
        config_list.append(f'{key}: {config_yaml[key]}')

    with open(os.path.join(process_dir, 'config.yaml'), 'w') as f:
        f.write('\n'.join(config_list))

    images_dir = os.path.join(process_dir, 'images')
    original_camera_models_overrides = os.path.join(images_dir, 'camera_models_overrides.json')
    camera_models_overrides = os.path.join(process_dir, 'camera_models_overrides.json')
    original_exif_overrides = os.path.join(images_dir, 'exif_overrides.json')
    exif_overrides = os.path.join(process_dir, 'exif_overrides.json')
    if os.path.exists(original_camera_models_overrides):
        shutil.copyfile(original_camera_models_overrides, camera_models_overrides)
    if os.path.exists(original_exif_overrides):
        shutil.copyfile(original_exif_overrides, exif_overrides)

    cmd = get_OpenSfM_bin()

    subprocess.run(cmd + ['extract_metadata', process_dir])
    remove_if_exists(camera_models_overrides)
    remove_if_exists(exif_overrides)
    subprocess.run(cmd + ['detect_features', process_dir])
    subprocess.run(cmd + ['match_features', process_dir])
    subprocess.run(cmd + ['create_tracks', process_dir])
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

    subprocess.run(cmd + ['undistort', process_dir])
    subprocess.run(cmd + ['compute_depthmaps', process_dir])
    subprocess.run(cmd + ['export_visualsfm', process_dir])

    end = time.time()
    elapsed_time = end - start
    logger.info(f"End of OpenSfM process in {elapsed_time} seconds")
