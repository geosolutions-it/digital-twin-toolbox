import numpy as np
import sys
import open3d as o3d

argv = sys.argv

input_xyz = argv[1]
output = argv[2]

depth = argv[3]
if not depth:
    depth = 10
else:
    depth = int(depth)

scale = argv[4]
if not scale:
    scale = 1.1
else:
    scale = float(scale)

remove_vertices_threshold = argv[5]
if not remove_vertices_threshold:
    remove_vertices_threshold = 1.1
else:
    remove_vertices_threshold = float(remove_vertices_threshold)

if __name__ == '__main__':

    point_cloud = np.loadtxt(input_xyz,skiprows=1,delimiter=',')
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(point_cloud[:,:3])
    pcd.colors = o3d.utility.Vector3dVector(point_cloud[:,3:6] / 255)

    distances = pcd.compute_nearest_neighbor_distance()
    average_distance = np.mean(distances)

    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=average_distance,max_nn=30))
    pcd.orient_normals_to_align_with_direction(orientation_reference=np.array([0., 0., 1.]))

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=depth, width=0, scale=scale, linear_fit=True)
    vertices_to_remove = densities < np.quantile(densities, remove_vertices_threshold)
    mesh.remove_vertices_by_mask(vertices_to_remove)

    bbox = pcd.get_axis_aligned_bounding_box()
    cropped_mesh = mesh.crop(bbox)

    o3d.io.write_triangle_mesh(output, mesh)

