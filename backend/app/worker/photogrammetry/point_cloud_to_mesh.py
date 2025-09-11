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
import time
from concurrent.futures import ThreadPoolExecutor

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

def get_tex_recon_bin():
    return ['/mvs-texturing/build/apps/texrecon/texrecon']

def process_point_cloud_partition(point_cloud_partition_dir, file):
    logger.info(f"Importing dense point cloud part: {file}")
    pipeline = pdal.Pipeline(json.dumps([
        {
            "type": "readers.las",
            "filename": os.path.join(point_cloud_partition_dir, file)
        },
        {
            "type": "filters.sample",
            "radius": 0.1
        },
        {
            "type": "filters.assign",
            "assignment": "Classification[:]=0"
        },
        {
            "type": "filters.outlier",
            "method": "statistical",
            "mean_k": 32,
            "multiplier": 2.2
        },
        {
            "type": "filters.range",
            "limits": "Classification![7:7]"
        },
        {
            "type": "writers.las",
            "filename": os.path.join(point_cloud_partition_dir, f"processed_{file}"),
            "extra_dims": "all"
        }
    ]))
    pipeline.execute()

def process_point_cloud(params):
    """Process point cloud to LAZ format"""

    process_dir = params.get('process_dir')
    dense_ply = params.get('dense_ply')
    output_xyz = params.get('output_xyz')
    max_workers = params.get('point_cloud_process_max_workers', 8)
    
    if os.path.exists(output_xyz):
        os.remove(output_xyz)

    point_cloud_partition_dir = os.path.join(process_dir, 'merged_parts')

    if os.path.exists(point_cloud_partition_dir):
        shutil.rmtree(point_cloud_partition_dir)
    os.mkdir(point_cloud_partition_dir)

    logger.info("Split dense point cloud")
    pipeline = pdal.Pipeline(json.dumps([
        {
            "type": "readers.ply",
            "filename": dense_ply
        },
        {
            "type": "filters.divider",
            "capacity": 5000000
        },
        {
            "type": "writers.las",
            "filename": os.path.join(point_cloud_partition_dir, 'out_#.laz'),
            "extra_dims": "all"
        }
    ]))
    pipeline.execute()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for file in os.listdir(point_cloud_partition_dir):
            executor.submit(process_point_cloud_partition, point_cloud_partition_dir, file)

    partitions = []

    for file in os.listdir(point_cloud_partition_dir):
        if 'processed_' in file:
            partitions.append(os.path.join(point_cloud_partition_dir, file))

    logger.info("Merge dense point cloud")

    pipeline = pdal.Pipeline(json.dumps(partitions + [
        {
            "type": "filters.merge"
        },
        # {
        #     "type": "writers.las",
        #     "filename": output_laz,
        #     "extra_dims": "all"
        # },
        {
            "type": 'writers.text',
            "format": 'csv',
            "order": 'X,Y,Z,NormalX,NormalY,NormalZ',
            "keep_unspecified": False,
            "filename": output_xyz
        }
    ]))
    pipeline.execute()

    if os.path.exists(point_cloud_partition_dir):
        shutil.rmtree(point_cloud_partition_dir)

def create_mesh(params):
    """Create mesh from point cloud"""
    depth = 11
    remove_vertices_threshold = 0.002
    input_xyz = params.get('output_xyz')
    output_ply = params.get('output_ply')

    if os.path.exists(output_ply):
        os.remove(output_ply)

    logger.info("Start conversion of dense point cloud to mesh")
    pcd = o3d.geometry.PointCloud()

    point_cloud = np.loadtxt(input_xyz,skiprows=1,delimiter=',')

    pcd.points = o3d.utility.Vector3dVector(point_cloud[:,:3])
    pcd.normals = o3d.utility.Vector3dVector(point_cloud[:,3:6])

    logger.info("Initialize poisson reconstruction")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd,
        depth=depth,
        n_threads=1,
        linear_fit=True
    )
    vertices_to_remove = densities < np.quantile(densities, remove_vertices_threshold)
    mesh.remove_vertices_by_mask(vertices_to_remove)
    logger.info("Poisson reconstruction completed")

    number_of_iterations = 10
    logger.info(f"Smooth surface with Taubin, number of iterations {number_of_iterations}")
    mesh = mesh.filter_smooth_taubin(number_of_iterations=number_of_iterations)
    mesh.compute_vertex_normals()

    target_number_of_triangles = 2560000 # 2^4 * 2^4 * 10000 -> 4 depth and 10000 faces tiles
    logger.info(f"Simplify mesh, target number of triangles {target_number_of_triangles}")
    mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_number_of_triangles)

    logger.info("Cropping mesh")
    bbox = pcd.get_axis_aligned_bounding_box()
    cropped_mesh = mesh.crop(bbox)

    logger.info("Exporting mesh")
    o3d.io.write_triangle_mesh(output_ply, cropped_mesh)

def create_texture(params):
    """Create textured mesh"""

    process_dir = params.get('process_dir')
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

    if os.path.exists(output_textured_dir_zip):
        os.remove(output_textured_dir_zip)

    if not os.path.exists(output_textured_dir_zip):
        shutil.make_archive(output_textured_dir, 'zip', output_textured_dir)
    
    logger.info("Created textured")

def run(process_dir, config):
    start = time.time()
    logger.info("Starting mesh generation process")

    dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged.ply')
    output_xyz = os.path.join(process_dir, 'merged.xyz')
    output_ply = os.path.join(process_dir, 'mesh.ply')
    output_textured_dir = os.path.join(process_dir, 'textured')
    output_textured_dir_zip = os.path.join(process_dir, 'textured.zip')

    force_delete = config.get('force_delete', False)
    if force_delete:
        logger.info("Starting fresh run - will overwrite existing outputs")
    else:
        logger.info("Resuming from previous run based on existing outputs")

    point_cloud_process_max_workers = 16
    params = {
        **config,
        'process_dir': process_dir,
        'dense_ply': dense_ply,
        'output_xyz': output_xyz,
        'output_ply': output_ply,
        'output_textured_dir': output_textured_dir,
        'output_textured_dir_zip': output_textured_dir_zip,
        'point_cloud_process_max_workers': point_cloud_process_max_workers
    }

    if force_delete or not os.path.exists(output_xyz):
        process_point_cloud(params)
    if force_delete or not os.path.exists(output_ply):
        create_mesh(params)
    if force_delete or not os.path.exists(output_textured_dir):
        create_texture(params)

    end = time.time()
    elapsed_time = end - start
    logger.info(f"Mesh conversion completed in {elapsed_time:.2f} seconds")
