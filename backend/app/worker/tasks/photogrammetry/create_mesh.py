import logging
import os
import numpy as np
import open3d as o3d

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run(params):
    """Poisson-reconstruct a mesh from the denoised dense point cloud (open3d)."""
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
