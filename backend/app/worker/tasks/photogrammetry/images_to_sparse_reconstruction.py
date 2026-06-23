
import logging
import os
import json
import time
import shutil
import numpy as np
from app.worker.tasks.photogrammetry.utils import (
    get_OpenSfM_bin, remove_if_exists, memory_available,
    create_config_for_stage, run_step, calculate_resource_allocation,
    survey_preset, sfm_config_yaml, SFM_PRESET_AERIAL, SFM_PRESET_HANDHELD
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run(process_dir, config):
    start = time.time()
    logger.info("Start OpenSfM process")
    force_delete = config.get('force_delete', False)
    auto_resolutions_computation = config.get('auto_resolutions_computation', True)
    create_statisitcs = config.get('create_statisitcs', False)

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

    resources = {
        "processes": int(config.get('processes')),
        "read_processes": int(config.get('read_processes')),
        "feature_process_size": int(config.get('feature_process_size')),
        "memory_mb": memory_available()
    }

    if auto_resolutions_computation:
        resources = calculate_resource_allocation(images_dir)

    logger.info(f"Resource allocation: {resources['processes']} processes, "
                f"{resources['feature_process_size']} feature process size")

    # survey type is auto-detected from OPK after extract_metadata; allow an explicit override
    aerial = config.get('aerial')

    # pre-extract config: keep altitude (detection is post-extract); rewritten before features
    pre_config = sfm_config_yaml(SFM_PRESET_HANDHELD, resources)
    pre_config['use_altitude_tag'] = 'yes'
    create_config_for_stage(process_dir, pre_config)

    original_camera_models_overrides = os.path.join(images_dir, 'camera_models_overrides.json')
    camera_models_overrides = os.path.join(process_dir, 'camera_models_overrides.json')
    original_exif_overrides = os.path.join(images_dir, 'exif_overrides.json')
    exif_overrides = os.path.join(process_dir, 'exif_overrides.json')

    original_masks_directory = os.path.join(images_dir, 'masks')
    masks_directory = os.path.join(process_dir, 'masks')

    if os.path.exists(original_masks_directory):
        shutil.copytree(original_masks_directory, masks_directory, dirs_exist_ok=True)

    if os.path.exists(original_camera_models_overrides):
        shutil.copyfile(original_camera_models_overrides, camera_models_overrides)
    if os.path.exists(original_exif_overrides):
        shutil.copyfile(original_exif_overrides, exif_overrides)

    cmd = get_OpenSfM_bin()

    if run_step('extract_metadata', cmd + ['extract_metadata', process_dir], process_dir):
        remove_if_exists(camera_models_overrides)
        remove_if_exists(exif_overrides)

    # select the preset from extracted metadata, then write the real config
    preset = survey_preset(process_dir, override=aerial)
    is_aerial = preset is SFM_PRESET_AERIAL
    logger.info(f"Survey type: {'aerial (OPK detected)' if is_aerial else 'handheld'}")
    create_config_for_stage(process_dir, sfm_config_yaml(preset, resources))

    run_step('detect_features', cmd + ['detect_features', process_dir], process_dir)
    run_step('match_features', cmd + ['match_features', process_dir], process_dir)
    run_step('create_tracks', cmd + ['create_tracks', process_dir], process_dir)
    run_step('reconstruct', cmd + ['reconstruct', '--algorithm', preset['reconstruct_algorithm'], process_dir], process_dir)


    # optional
    if create_statisitcs:
        run_step('compute_statistics', cmd + ['compute_statistics', process_dir], process_dir)
        run_step('export_report', cmd + ['export_report', process_dir], process_dir)
        run_step('export_ply', cmd + ['export_ply', process_dir], process_dir)
    # end -- optional

    reconstruction = None
    reconstruction_path = os.path.join(process_dir, 'reconstruction.json')
    if os.path.exists(reconstruction_path):
        with open(reconstruction_path, 'r') as f:
            reconstruction = json.load(f)

    if not reconstruction:
        raise RuntimeError(
            "OpenSfM produced no reconstruction (reconstruction.json is empty). "
            "Likely no feature matches / insufficient image overlap. Check the "
            "detect_features and match_features logs for feature and match counts."
        )

    cameras_path = os.path.join(process_dir, 'camera_models.json')
    remove_if_exists(cameras_path)

    cameras = reconstruction[0].get('cameras')
    with open(cameras_path, 'w') as f:
        json.dump(cameras, f, indent=4)

    end = time.time()
    elapsed_time = end - start
    logger.info(f"End of sparse reconstruction process in {elapsed_time} seconds")