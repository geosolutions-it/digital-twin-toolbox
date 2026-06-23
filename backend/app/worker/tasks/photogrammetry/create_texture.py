import logging
import os
import subprocess
import shutil
from app.worker.tasks.photogrammetry.utils import (
    get_OpenSfM_bin, run_step, create_config_for_stage
)
from app.worker.common.utils import run_subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_tex_recon_bin():
    return ['/mvs-texturing/build/apps/texrecon/texrecon']


def run(params):
    """Texture the mesh (OpenSfM undistort/export + mvs-texturing texrecon)."""

    process_dir = params.get('process_dir')

    depthmap_resolution = params.get('depthmap_resolution')
    texture_image_resolution = params.get('texture_image_resolution')
    texture_image_processes = params.get('texture_image_processes', 1)
    cmd = get_OpenSfM_bin()
    if depthmap_resolution != texture_image_resolution:
        config_yaml = {
            'undistorted_image_max_size': texture_image_resolution,
            'undistorted_image_format': 'jpg',
            'processes': texture_image_processes,
            'read_processes': texture_image_processes,
        }
        create_config_for_stage(process_dir, config_yaml)
        undistorted_images_dir = os.path.join(process_dir, 'undistorted', 'images')
        if os.path.exists(undistorted_images_dir):
            shutil.rmtree(undistorted_images_dir)
        run_step('undistort', cmd + ['undistort', process_dir], process_dir, skip_check=True)

    visual_sfm_path = os.path.join(process_dir, 'undistorted', 'reconstruction.nvm')
    if os.path.exists(visual_sfm_path):
        os.remove(visual_sfm_path)
    run_step('export_visualsfm', cmd + ['export_visualsfm', process_dir], process_dir, skip_check=True)
    output_textured_dir = params.get('output_textured_dir')
    output_textured_dir_zip = params.get('output_textured_dir_zip')
    output_ply = params.get('output_ply')

    reconstruction_nvm = os.path.join(process_dir, 'undistorted', 'reconstruction.nvm')

    if os.path.exists(output_textured_dir):
        shutil.rmtree(output_textured_dir)

    if os.path.exists(output_textured_dir_zip):
        os.remove(output_textured_dir_zip)

    if not os.path.exists(output_textured_dir):
        os.mkdir(output_textured_dir)

    output_textured_mesh = os.path.join(output_textured_dir, 'mesh')

    run_subprocess(get_tex_recon_bin() + [
        reconstruction_nvm,
        output_ply,
        output_textured_mesh,
        '-d', 'gmi',
        '-o', 'gauss_clamping',
        '-t', 'none',
        '--no_intermediate_results',
        '--keep_unseen_faces',
        '--num_threads=1'
    ])

    if os.path.exists(output_textured_dir_zip):
        os.remove(output_textured_dir_zip)

    if not os.path.exists(output_textured_dir_zip):
        shutil.make_archive(output_textured_dir, 'zip', output_textured_dir)

    logger.info("Created textured")
