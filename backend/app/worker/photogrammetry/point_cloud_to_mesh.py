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
# end from opensfm

def transformation_to_string(transformation):
    string = []
    for row in transformation:
        for col in row:
            string.append(f"{col}")

    return " ".join(string)

def transform_extent_to_local(reference_lla, config):

    if not config or not reference_lla:
        return None
    projection = config.get('projection')
    extent = config.get('extent')
    if not projection or not extent:
        return None
    reference = TopocentricConverter(
        reference_lla["latitude"],
        reference_lla["longitude"],
        reference_lla["altitude"]
    )
    projection = pyproj.Proj(projection)
    t = _get_transformation(reference, projection)
    t_inv = np.linalg.inv(t)

    xmin, ymin = projection(extent[0], extent[1])
    xmax, ymax = projection(extent[2], extent[3])

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
    pcd.colors = o3d.utility.Vector3dVector(to_2D_array(points[['Red', 'Green', 'Blue']]))
    pcd.normals = o3d.utility.Vector3dVector(to_2D_array(points[['NormalX', 'NormalY', 'NormalZ']]))

    # logger.info("Computing average distance")
    # distances = pcd.compute_nearest_neighbor_distance()
    # average_distance = np.mean(distances)
    # logger.info(f"Average distance: {average_distance}")

    # logger.info("Down sample of point cloud")
    # voxel_size_multipler = 0.15
    # voxel_size = average_distance * voxel_size_multipler
    # pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size)

    # cl, ind = pcd_down.remove_statistical_outlier(nb_neighbors=8, std_ratio=2)
    # pcd_filtered_stat = pcd_down.select_by_index(ind)

    logger.info("Initialize poisson reconstruction")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=depth, n_threads=1, linear_fit=True)
    vertices_to_remove = densities < np.quantile(densities, remove_vertices_threshold)
    mesh.remove_vertices_by_mask(vertices_to_remove)
    logger.info("Poisson reconstruction completed")

    # mesh.filter_smooth_simple(number_of_iterations=3)
    # mesh.filter_smooth_laplacian(number_of_iterations=2)
    number_of_iterations = 10
    logger.info(f"Smooth surface with Taubin, number of iterations {number_of_iterations}")
    mesh = mesh.filter_smooth_taubin(number_of_iterations=number_of_iterations)
    mesh.compute_vertex_normals()

    target_number_of_triangles = 2000000
    logger.info(f"Simplify mesh, target number of triangles {target_number_of_triangles}")
    mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_number_of_triangles)

    # with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Debug) as cm:
    #     triangle_clusters, cluster_n_triangles, cluster_area = mesh.cluster_connected_triangles()
    #     triangle_clusters = np.asarray(triangle_clusters)
    #     cluster_n_triangles = np.asarray(cluster_n_triangles)
    #     largest_cluster_idx = cluster_n_triangles.argmax()
    #     triangles_to_remove = triangle_clusters != largest_cluster_idx
    #     mesh.remove_triangles_by_mask(triangles_to_remove)

    logger.info("Cropping mesh")
    bbox = pcd.get_axis_aligned_bounding_box()
    cropped_mesh = mesh.crop(bbox)

    logger.info("Exporting mesh")
    o3d.io.write_triangle_mesh(output_ply, cropped_mesh)

def run(process_dir):

    dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged.ply')

    output_ply = os.path.join(process_dir, 'mesh.ply')
    if os.path.exists(output_ply):
        os.remove(output_ply)

    output_laz = os.path.join(process_dir, 'merged.laz')
    if os.path.exists(output_laz):
        os.remove(output_laz)

    reference_lla = None
    reference_lla_path = os.path.join(process_dir, 'reference_lla.json')
    with open(reference_lla_path, 'r') as f:
        reference_lla = json.load(f)

    config = None
    config_path = os.path.join(process_dir, 'images', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)

    pipeline = [
        {
            "type": "readers.ply",
            "filename": dense_ply
        },
    ]

    local_extent = transform_extent_to_local(reference_lla, config)
    if local_extent:
        xmin, ymin = (local_extent[0], local_extent[1])
        xmax, ymax = (local_extent[2], local_extent[3])
        logger.info(f"Local extent: ([{xmin},{xmax}],[{ymin},{ymax}])")
        pipeline += [
            {
                "type": "filters.crop",
                "bounds": f"([{xmin},{xmax}],[{ymin},{ymax}])"
            },
        ]


    pipeline += [
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
            "method": "radius",
            "radius": 0.75, # too low, we need to find good balance
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
    points = pipeline.arrays[0]

    xyz_to_mesh(points, output_ply)

    logger.info("Create mesh texture")
    reconstruction_nvm = os.path.join(process_dir, 'undistorted', 'reconstruction.nvm')
    output_textured_dir = os.path.join(process_dir, 'textured')
    if os.path.exists(output_textured_dir):
        shutil.rmtree(output_textured_dir)
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
        '--num_threads=1'
    ])
    logger.info("Mesh conversion completed")
