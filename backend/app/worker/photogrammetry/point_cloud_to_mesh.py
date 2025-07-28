import logging
import sys
import os
import numpy as np
import pyproj
import json
import pdal
import open3d as o3d
import subprocess
import shutil
import cv2
from PIL import Image
from pyproj import CRS
import time
import app.worker.photogrammetry.mesh_to_3dtile as mesh_to_3dtile
import bpy
import laspy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

argv = sys.argv

WGS84_a = 6378137.0
WGS84_b = 6356752.314245

# from opensfm
def ecef_from_lla(lat, lon, alt):
    """
    Compute ECEF XYZ from latitude, longitude and altitude.

    All using the WGS84 model.
    Altitude is the distance to the WGS84 ellipsoid.
    Check results here http://www.oc.nps.edu/oc2902w/coord/llhxyz.htm

    >>> lat, lon, alt = 10, 20, 30
    >>> x, y, z = ecef_from_lla(lat, lon, alt)
    >>> np.allclose(lla_from_ecef(x,y,z), [lat, lon, alt])
    True
    """
    a2 = WGS84_a**2
    b2 = WGS84_b**2
    lat = np.radians(lat)
    lon = np.radians(lon)
    L = 1.0 / np.sqrt(a2 * np.cos(lat) ** 2 + b2 * np.sin(lat) ** 2)
    x = (a2 * L + alt) * np.cos(lat) * np.cos(lon)
    y = (a2 * L + alt) * np.cos(lat) * np.sin(lon)
    z = (b2 * L + alt) * np.sin(lat)
    return x, y, z


def lla_from_ecef(x, y, z):
    """
    Compute latitude, longitude and altitude from ECEF XYZ.

    All using the WGS84 model.
    Altitude is the distance to the WGS84 ellipsoid.
    """
    a = WGS84_a
    b = WGS84_b
    ea = np.sqrt((a**2 - b**2) / a**2)
    eb = np.sqrt((a**2 - b**2) / b**2)
    p = np.sqrt(x**2 + y**2)
    theta = np.arctan2(z * a, p * b)
    lon = np.arctan2(y, x)
    lat = np.arctan2(
        z + eb**2 * b * np.sin(theta) ** 3, p - ea**2 * a * np.cos(theta) ** 3
    )
    N = a / np.sqrt(1 - ea**2 * np.sin(lat) ** 2)
    alt = p / np.cos(lat) - N
    return np.degrees(lat), np.degrees(lon), alt


def ecef_from_topocentric_transform(lat, lon, alt):
    """
    Transformation from a topocentric frame at reference position to ECEF.

    The topocentric reference frame is a metric one with the origin
    at the given (lat, lon, alt) position, with the X axis heading east,
    the Y axis heading north and the Z axis vertical to the ellipsoid.
    >>> a = ecef_from_topocentric_transform(30, 20, 10)
    >>> b = ecef_from_topocentric_transform_finite_diff(30, 20, 10)
    >>> np.allclose(a, b)
    True
    """
    x, y, z = ecef_from_lla(lat, lon, alt)
    sa = np.sin(np.radians(lat))
    ca = np.cos(np.radians(lat))
    so = np.sin(np.radians(lon))
    co = np.cos(np.radians(lon))
    return np.array(
        [
            [-so, -sa * co, ca * co, x],
            [co, -sa * so, ca * so, y],
            [0, ca, sa, z],
            [0, 0, 0, 1],
        ]
    )


def ecef_from_topocentric_transform_finite_diff(lat, lon, alt):
    """
    Transformation from a topocentric frame at reference position to ECEF.

    The topocentric reference frame is a metric one with the origin
    at the given (lat, lon, alt) position, with the X axis heading east,
    the Y axis heading north and the Z axis vertical to the ellipsoid.
    """
    eps = 1e-2
    x, y, z = ecef_from_lla(lat, lon, alt)
    v1 = (
        (
            np.array(ecef_from_lla(lat, lon + eps, alt))
            - np.array(ecef_from_lla(lat, lon - eps, alt))
        )
        / 2
        / eps
    )
    v2 = (
        (
            np.array(ecef_from_lla(lat + eps, lon, alt))
            - np.array(ecef_from_lla(lat - eps, lon, alt))
        )
        / 2
        / eps
    )
    v3 = (
        (
            np.array(ecef_from_lla(lat, lon, alt + eps))
            - np.array(ecef_from_lla(lat, lon, alt - eps))
        )
        / 2
        / eps
    )
    v1 /= np.linalg.norm(v1)
    v2 /= np.linalg.norm(v2)
    v3 /= np.linalg.norm(v3)
    return np.array(
        [
            [v1[0], v2[0], v3[0], x],
            [v1[1], v2[1], v3[1], y],
            [v1[2], v2[2], v3[2], z],
            [0, 0, 0, 1],
        ]
    )


def topocentric_from_lla(lat, lon, alt, reflat, reflon, refalt):
    """
    Transform from lat, lon, alt to topocentric XYZ.

    >>> lat, lon, alt = -10, 20, 100
    >>> np.allclose(topocentric_from_lla(lat, lon, alt, lat, lon, alt),
    ...     [0,0,0])
    True
    >>> x, y, z = topocentric_from_lla(lat, lon, alt, 0, 0, 0)
    >>> np.allclose(lla_from_topocentric(x, y, z, 0, 0, 0),
    ...     [lat, lon, alt])
    True
    """
    T = np.linalg.inv(ecef_from_topocentric_transform(reflat, reflon, refalt))
    x, y, z = ecef_from_lla(lat, lon, alt)
    tx = T[0, 0] * x + T[0, 1] * y + T[0, 2] * z + T[0, 3]
    ty = T[1, 0] * x + T[1, 1] * y + T[1, 2] * z + T[1, 3]
    tz = T[2, 0] * x + T[2, 1] * y + T[2, 2] * z + T[2, 3]
    return tx, ty, tz


def lla_from_topocentric(x, y, z, reflat, reflon, refalt):
    """
    Transform from topocentric XYZ to lat, lon, alt.
    """
    T = ecef_from_topocentric_transform(reflat, reflon, refalt)
    ex = T[0, 0] * x + T[0, 1] * y + T[0, 2] * z + T[0, 3]
    ey = T[1, 0] * x + T[1, 1] * y + T[1, 2] * z + T[1, 3]
    ez = T[2, 0] * x + T[2, 1] * y + T[2, 2] * z + T[2, 3]
    return lla_from_ecef(ex, ey, ez)


def gps_distance(latlon_1, latlon_2):
    """
    Distance between two (lat,lon) pairs.

    >>> p1 = (42.1, -11.1)
    >>> p2 = (42.2, -11.3)
    >>> 19000 < gps_distance(p1, p2) < 20000
    True
    """
    x1, y1, z1 = ecef_from_lla(latlon_1[0], latlon_1[1], 0.0)
    x2, y2, z2 = ecef_from_lla(latlon_2[0], latlon_2[1], 0.0)

    dis = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)

    return dis


class TopocentricConverter:
    """Convert to and from a topocentric reference frame."""

    def __init__(self, reflat, reflon, refalt):
        """Init the converter given the reference origin."""
        self.lat = reflat
        self.lon = reflon
        self.alt = refalt

    def to_topocentric(self, lat, lon, alt):
        """Convert lat, lon, alt to topocentric x, y, z."""
        return topocentric_from_lla(lat, lon, alt, self.lat, self.lon, self.alt)

    def to_lla(self, x, y, z):
        """Convert topocentric x, y, z to lat, lon, alt."""
        return lla_from_topocentric(x, y, z, self.lat, self.lon, self.alt)

    def __eq__(self, o):
        return np.allclose([self.lat, self.lon, self.alt], (o.lat, o.lon, o.alt))

def _transform(point, reference, projection):
    """Transform on point from local coords to a proj4 projection."""
    lat, lon, altitude = reference.to_lla(point[0], point[1], point[2])
    easting, northing = projection(lon, lat)
    return [easting, northing, altitude]

def _get_transformation(reference, projection) :
    """Get the linear transform from reconstruction coords to geocoords."""
    p = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]
    q = [_transform(point, reference, projection) for point in p]

    transformation = np.array(
        [
            [q[0][0] - q[3][0], q[1][0] - q[3][0], q[2][0] - q[3][0], q[3][0]],
            [q[0][1] - q[3][1], q[1][1] - q[3][1], q[2][1] - q[3][1], q[3][1]],
            [q[0][2] - q[3][2], q[1][2] - q[3][2], q[2][2] - q[3][2], q[3][2]],
            [0, 0, 0, 1],
        ]
    )
    return transformation


def transformation_to_string(transformation):
    string = []
    for row in transformation:
        for col in row:
            string.append(f"{col}")

    return " ".join(string)

def get_transformation_matrix(reference_lla, projection):
    reference = TopocentricConverter(
        reference_lla["latitude"],
        reference_lla["longitude"],
        reference_lla["altitude"]
    )
    pyproj_projection = pyproj.Proj(projection)
    t = _get_transformation(reference, pyproj_projection)
    t_inv = np.linalg.inv(t)
    return [t, t_inv]

def transform_extent_to_local(reference_lla, config):

    if not config or not reference_lla:
        return None
    projection = config.get('projection')
    extent = config.get('extent')
    if not projection or not extent:
        return None
    pyproj_projection = pyproj.Proj(projection)
    t, t_inv = get_transformation_matrix(reference_lla, projection)

    xmin, ymin = pyproj_projection(extent[0], extent[1])
    xmax, ymax = pyproj_projection(extent[2], extent[3])

    proj_extent = [xmin, ymin, xmax, ymax]

    corners = [
        [proj_extent[0], proj_extent[1], 0, 1],  # bottom-left
        [proj_extent[2], proj_extent[1], 0, 1],  # bottom-right
        [proj_extent[2], proj_extent[3], 0, 1],  # top-right
        [proj_extent[0], proj_extent[3], 0, 1],  # top-left
    ]

    transformed = [t_inv @ np.array(p).T for p in corners]

    xs = [p[0] for p in transformed]
    ys = [p[1] for p in transformed]

    transformed_extent = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]

    return transformed_extent

def to_2D_array(arr):
    t = arr.astype(object)
    return np.array([*t])

def get_tex_recon_bin():
    return ['/mvs-texturing/build/apps/texrecon/texrecon']

def xyz_to_mesh(points, output_ply):

    depth = 11
    remove_vertices_threshold = 0.002

    logger.info("Start conversion of dense point cloud to mesh")
    pcd = o3d.geometry.PointCloud()

    pcd.points = o3d.utility.Vector3dVector(to_2D_array(points[['X', 'Y', 'Z']]))
    pcd.colors = o3d.utility.Vector3dVector(to_2D_array(points[['Red', 'Green', 'Blue']]) / 255)
    pcd.normals = o3d.utility.Vector3dVector(to_2D_array(points[['NormalX', 'NormalY', 'NormalZ']]))

    logger.info("Initialize poisson reconstruction")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=depth, n_threads=1, linear_fit=True)
    vertices_to_remove = densities < np.quantile(densities, remove_vertices_threshold)
    mesh.remove_vertices_by_mask(vertices_to_remove)
    logger.info("Poisson reconstruction completed")

    number_of_iterations = 10
    logger.info(f"Smooth surface with Taubin, number of iterations {number_of_iterations}")
    mesh = mesh.filter_smooth_taubin(number_of_iterations=number_of_iterations)
    mesh.compute_vertex_normals()

    target_number_of_triangles = 2000000
    logger.info(f"Simplify mesh, target number of triangles {target_number_of_triangles}")
    mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_number_of_triangles)

    logger.info("Cropping mesh")
    bbox = pcd.get_axis_aligned_bounding_box()
    cropped_mesh = mesh.crop(bbox)

    logger.info("Exporting mesh")
    o3d.io.write_triangle_mesh(output_ply, cropped_mesh)


def downscale_images(source_dir, target_dir, target_resolution):
    """
    Downscale images from source directory to target directory.

    Args:
        source_dir (str): Directory containing source images
        target_dir (str): Directory where downscaled images will be saved
        target_resolution (int): Target resolution (max dimension) for downscaled images

    Returns:
        int: Number of images processed
    """
    logger.info(f"Downscaling images to max dimension of {target_resolution}px")

    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    image_count = 0
    supported_extensions = ('.jpg', '.png', '.tif', '.jpeg')

    for fname in os.listdir(source_dir):
        if fname.lower().endswith(supported_extensions):
            image_path = os.path.join(source_dir, fname)
            target_path = os.path.join(target_dir, fname)

            img = cv2.imread(image_path)
            if img is None:
                logger.warning(f"Failed to read image: {image_path}")
                continue

            h, w = img.shape[:2]
            scale = target_resolution / max(h, w)

            if scale < 1.0:
                img_resized = cv2.resize(img, (int(w * scale), int(h * scale)))
                logger.debug(f"Downscaled {fname} from {w}x{h} to {int(w * scale)}x{int(h * scale)}")
            else:
                img_resized = img
                logger.debug(f"Kept original size for {fname} ({w}x{h})")

            cv2.imwrite(target_path, img_resized)
            image_count += 1

    logger.info(f"Downscaled {image_count} images to {target_dir}")
    return image_count

def process_nvm_file(input_nvm_path, output_nvm_path, images_dir, texture_image_resolution ):
    """
    Process NVM file to create a downscaled version.

    Args:
        input_nvm_path: Path to the input NVM file
        output_nvm_path: Path to the output NVM file
        images_dir: Directory containing the original images
        texture_image_resolution: Resolution for the texture images (e.g., 2048)
    """

    with open(input_nvm_path, 'r') as f:
        lines = f.readlines()

    header_lines = []
    i = 0
    while i < len(lines) and not lines[i].strip().isdigit():
        header_lines.append(lines[i])
        i += 1

    num_images = int(lines[i].strip())
    i += 1

    new_image_lines = []
    for _ in range(num_images):
        if i >= len(lines):
            break

        line = lines[i].strip()
        if not line:
            break

        parts = line.split(' ')

        img_path = parts[0]
        img_filename = os.path.basename(img_path)
        new_img_path = f"images_downsample/{img_filename}"

        try:
            full_img_path = os.path.join(images_dir, img_filename)
            with Image.open(full_img_path) as img:
                width, height = img.size

            max_dimension = max(width, height)

            original_focal = float(parts[1])

            focal_ratio = original_focal / max_dimension
            new_focal_length = texture_image_resolution * focal_ratio

            parts[0] = new_img_path
            parts[1] = f"{new_focal_length}"

            new_image_lines.append(' '.join(parts))

        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            new_image_lines.append(line)

        i += 1

    footer_lines = lines[i:]
    with open(output_nvm_path, 'w') as f:
        for line in header_lines:
            f.write(line)

        f.write(f"{len(new_image_lines)}\n")

        for line in new_image_lines:
            f.write(f"{line}\n")

        for line in footer_lines:
            f.write(line)

    print(f"Created {output_nvm_path} with {len(new_image_lines)} images")


def get_completed_steps(process_dir: str):
    """Read completion markers to determine completed steps"""
    completed_steps = {}

    output_laz = os.path.join(process_dir, 'merged.laz')
    if os.path.exists(output_laz):
        completed_steps['process_pointcloud'] = True
    
    output_ply = os.path.join(process_dir, 'mesh.ply')
    if os.path.exists(output_ply):
        completed_steps['create_mesh'] = True
    
    output_textured_dir_zip = os.path.join(process_dir, 'textured.zip')
    if os.path.exists(output_textured_dir_zip):
        completed_steps['create_texture'] = True
    
    preview_file = os.path.join(process_dir, 'preview','0_0_0.glb')
    if os.path.exists(preview_file):
        completed_steps['create_preview'] = True

    logger.info(f"Found completed steps: {list(completed_steps.keys())}")
    return completed_steps


def run_step(step_name, func, *args, **kwargs):
    """Run a processing step if it hasn't been completed yet"""
    process_dir = args[0] if args else kwargs.get('process_dir', '')
    force_delete = kwargs.pop('force_delete', False) if 'force_delete' in kwargs else False
    completed_steps = get_completed_steps(process_dir)
    
    if step_name in completed_steps and not force_delete:
        logger.info(f"Skipping already completed step: {step_name}")
        return True
    
    logger.info(f"Running step: {step_name}")
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Step {step_name} failed: {e}")
        return False

def process_point_cloud(process_dir, config, to_ellipsoidal_height=True):
    """Process point cloud to LAZ format"""
    cropped_dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged_cropped.ply')
    output_laz = os.path.join(process_dir, 'merged.laz')
    
    if os.path.exists(output_laz) and config.get('force_delete', False):
        os.remove(output_laz)
    
    reference_lla = None
    reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
    with open(reference_lla_path, 'r') as f:
        reference_lla = json.load(f)

    config_data = None
    config_path = os.path.join(process_dir, 'images', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = json.load(f)

    pipeline = [
        {
            "type": "readers.ply",
            "filename": cropped_dense_ply
        },
    ]

    pipeline += [
        {
            "type": "filters.assign",
            "assignment": "Classification[:]=0"
        },
        {
            "type": "filters.outlier",
            "method": "radius",
            "radius": 0.75,
            "min_k": 4
        },
        {
            "type": "filters.range",
            "limits": "Classification![7:7]"
        },
        {
            "type": "writers.las",
            "filename": output_laz,
            "extra_dims": "all"
        }
    ]

    logger.info("Importing dense point cloud")
    pipeline = pdal.Pipeline(json.dumps(pipeline))
    pipeline.execute()
    return True



def create_mesh(process_dir, config):
    """Create mesh from point cloud"""
    cropped_dense_laz = os.path.join(process_dir, 'merged.laz')
    if not os.path.exists(cropped_dense_laz):
        logger.error(f"Point cloud file {cropped_dense_laz} does not exist. Please run process_point_cloud first.")
        return False

    pipeline =[
        {
            "type": "readers.las",
            "filename": cropped_dense_laz
        }
    ]

    pipeline = pdal.Pipeline(json.dumps(pipeline))
    pipeline.execute()
    points = pipeline.arrays[0]
    output_ply = os.path.join(process_dir, 'mesh.ply')
    
    if os.path.exists(output_ply) and config.get('force_delete', False):
        os.remove(output_ply)
        
    xyz_to_mesh(points, output_ply)
    return True



def create_texture(process_dir, config):
    """Create textured mesh"""
    texture_image_downsample = False
    texture_image_resolution = config.get('texture_image_resolution', 4096)

    if texture_image_downsample:
        undistorted_images_dir = os.path.join(process_dir, 'undistorted', 'images')
        downsampled_images_dir = os.path.join(process_dir, 'undistorted', 'images_downsample')
        downscale_images(undistorted_images_dir, downsampled_images_dir, texture_image_resolution)

        input_nvm = os.path.join(process_dir, 'undistorted', 'reconstruction.nvm')
        output_nvm = os.path.join(process_dir, 'undistorted', 'reconstruction_downsample.nvm')
        process_nvm_file(input_nvm, output_nvm, undistorted_images_dir, texture_image_resolution)

    reconstruction_nvm = os.path.join(
        process_dir, 
        'undistorted', 
        'reconstruction_downsample.nvm' if texture_image_downsample else 'reconstruction.nvm'
    )

    output_textured_dir = os.path.join(process_dir, 'textured')
    if os.path.exists(output_textured_dir) and config.get('force_delete', False):
        shutil.rmtree(output_textured_dir)
    
    if not os.path.exists(output_textured_dir):
        os.mkdir(output_textured_dir)
        
    output_textured_mesh = os.path.join(output_textured_dir, 'mesh')
    output_ply = os.path.join(process_dir, 'mesh.ply')
    
    subprocess.run(get_tex_recon_bin() + [
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
    
    output_textured_dir_zip = os.path.join(process_dir, 'textured.zip')
    if os.path.exists(output_textured_dir_zip) and config.get('force_delete', False):
        os.remove(output_textured_dir_zip)
        
    print(f"Created textured ")
    if not os.path.exists(output_textured_dir_zip):
        shutil.make_archive(output_textured_dir, 'zip', output_textured_dir)
        
    return True

def create_preview_mesh(process_dir, config):
    try:   
        output_tiles = os.path.join(process_dir, 'preview')
        os.makedirs(output_tiles, exist_ok=True)
        mesh_to_3dtile.run(process_dir,output_tiles,depth=0,tileset=False, tile_faces_target= 90000)
        return True
    except ImportError as e:
        logger.error(f"Failed to import mesh_to_3dtile: {e}")
        return False
    except Exception as e:
        logger.error(f"Error creating preview mesh: {e}")
        return False

def run(process_dir, config):
    start = time.time()
    logger.info("Starting mesh generation process")

    force_delete = config.get('force_delete', False)
    if force_delete:
        logger.info("Starting fresh run - will overwrite existing outputs")
    else:
        logger.info("Resuming from previous run based on existing outputs")
    
    run_step('process_pointcloud', process_point_cloud, process_dir, config, force_delete=force_delete)
    run_step('create_mesh', create_mesh, process_dir, config, force_delete=force_delete)
    run_step('create_texture', create_texture, process_dir, config, force_delete=force_delete)
    run_step('create_preview', create_preview_mesh, process_dir, config, force_delete=force_delete)
    
    end = time.time()
    elapsed_time = end - start
    logger.info(f"Mesh conversion completed in {elapsed_time:.2f} seconds")