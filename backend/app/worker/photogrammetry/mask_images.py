import logging
import os
import json
import cv2
import numpy as np
from app.worker.photogrammetry.point_cloud_to_mesh import transform_extent_to_local
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run(process_dir):

    reference_lla = None
    reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
    with open(reference_lla_path, 'r') as f:
        reference_lla = json.load(f)

    config = None
    config_path = os.path.join(process_dir, 'images', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)

    reconstruction = None
    reconstruction_path = os.path.join(process_dir, 'reconstruction.json')
    if os.path.exists(reconstruction_path):
        with open(reconstruction_path, 'r') as f:
            reconstruction = json.load(f)

    masks_dir = os.path.join(process_dir, 'masks')
    if os.path.exists(masks_dir):
        shutil.rmtree(masks_dir)
    os.mkdir(masks_dir)

    cameras = reconstruction[0].get('cameras')
    shots = reconstruction[0].get('shots')

    if config:
        extent = config.get('extent')
        if extent and len(extent) > 5:
            local_extent = transform_extent_to_local(reference_lla, config)
            zmin = extent[4]
            zmax = extent[5]
            points = np.array([
                # bottom plane
                [local_extent[0], local_extent[1], zmin],
                [local_extent[0], local_extent[3], zmin],
                [local_extent[2], local_extent[3], zmin],
                [local_extent[2], local_extent[1], zmin],
                # top plane
                [local_extent[0], local_extent[1], zmax],
                [local_extent[0], local_extent[3], zmax],
                [local_extent[2], local_extent[3], zmax],
                [local_extent[2], local_extent[1], zmax]
            ], np.float32)
            logger.info("Creating masks based on extent volume")
            for key in shots:

                shot = shots.get(key)
                camera = cameras.get(shot.get('camera'))

                camera_matrix = np.array([
                    [camera.get('focal_x'), 0, camera.get('c_x', 0)],
                    [0, camera.get('focal_y'), camera.get('c_y', 0)],
                    [0, 0, 1]], np.float32)
                rvec = np.array(shot.get('rotation'), np.float32)
                tvec = np.array(shot.get('translation'), np.float32)
                dist_coeffs = np.array([
                    camera.get('k1', 0),
                    camera.get('k2', 0),
                    camera.get('p1', 0),
                    camera.get('p2', 0),
                    camera.get('k3', 0)
                ], np.float32)

                points_2d, _ = cv2.projectPoints(points,
                    rvec, tvec,
                    camera_matrix,
                    dist_coeffs)
                hull = cv2.convexHull(points_2d)

                img = cv2.imread(os.path.join(process_dir, 'images', key))
                height, width = img.shape[:2]
                resolution = max(height, width)
                mask_img = np.zeros((height, width, 3), np.uint8)
                poly = []
                for point in hull:
                    poly.append([
                        point[0][0] * resolution + width / 2,
                        point[0][1] * resolution + height / 2
                    ])
                cv2.fillPoly(mask_img, np.array([poly], dtype=np.int32), (255, 255, 255))
                cv2.imwrite(os.path.join(masks_dir, f"{key}.png"), mask_img)
    else:
        logger.info("Extent volume not available skipping masks creation")
