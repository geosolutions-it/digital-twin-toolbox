
import subprocess
import os
import json
import time
import sys

argv = sys.argv

def remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)

def run_sparse_point_cloud(opensfm_path, tile_id):
    start = time.time()
    output_dir = os.path.join('output', tile_id)
    cmd = os.path.join(opensfm_path, 'bin', 'opensfm')
    subprocess.run([cmd, 'extract_metadata', output_dir])
    remove_if_exists(os.path.join(output_dir, 'camera_models_overrides.json'))
    remove_if_exists(os.path.join(output_dir, 'exif_overrides.json'))
    subprocess.run([cmd, 'detect_features', output_dir])
    subprocess.run([cmd, 'match_features', output_dir])
    subprocess.run([cmd, 'create_tracks', output_dir])
    subprocess.run([cmd, 'reconstruct', '--algorithm', 'triangulation', output_dir])

    subprocess.run([cmd, 'compute_statistics', output_dir])
    subprocess.run([cmd, 'export_report', output_dir])

    subprocess.run([cmd, 'export_ply', output_dir])

    reconstruction = None
    with open(os.path.join(output_dir, 'reconstruction.json'), 'r') as f:
        reconstruction = json.load(f)

    cameras_path = os.path.join(output_dir, 'camera_models.json')
    remove_if_exists(cameras_path)

    cameras = reconstruction[0].get('cameras')
    with open(cameras_path, 'w') as f:
        json.dump(cameras, f, indent=4)

    subprocess.run([cmd, 'undistort', output_dir])
    subprocess.run([cmd, 'compute_depthmaps', output_dir])
    subprocess.run([cmd, 'export_visualsfm', output_dir])

    end = time.time()
    elapsed_time = end - start
    print(f"Processed in {elapsed_time} seconds")


if __name__ == '__main__':

    run_sparse_point_cloud('/source/OpenSfM', argv[1])

