import open3d as o3d
import numpy as np

depth = 10
scale = 1.1
remove_vertices_threshold = 0.002
voxel_size_multipler = 0.15

input_xyz = ""
output = ""

point_cloud = np.loadtxt(input_xyz,skiprows=1,delimiter=',')
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(point_cloud[:,:3])
pcd.colors = o3d.utility.Vector3dVector(point_cloud[:,3:6] / 255)
pcd.normals = o3d.utility.Vector3dVector(point_cloud[:,6:9])

print(f"Total number of points: {len(pcd.points)}")

distances = pcd.compute_nearest_neighbor_distance()
average_distance = np.mean(distances)
print(f"Average distance: {average_distance}")

voxel_size = average_distance * voxel_size_multipler
pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size)

print(f"Downsample to :{len(pcd_down.points)} , Number of points removed :{len(pcd.points) - len(pcd_down.points)}")

cl, ind = pcd_down.remove_statistical_outlier(nb_neighbors=8, std_ratio=2)
pcd_filtered_stat = pcd_down.select_by_index(ind)
o3d.visualization.draw_geometries([pcd_filtered_stat])

print(f"Downsample  after statistical filtering :{len(pcd_filtered_stat.points)}, Number of points removed :{len(pcd.points) - len(pcd_filtered_stat.points)}")

mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd_filtered_stat, depth=depth, n_threads=1,linear_fit=True)
vertices_to_remove = densities < np.quantile(densities, remove_vertices_threshold)
mesh.remove_vertices_by_mask(vertices_to_remove)

# Mesh optimization
mesh.filter_smooth_simple(number_of_iterations=3)
mesh.filter_smooth_laplacian(number_of_iterations=2)

# Remove small floating components
with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Debug) as cm:
    triangle_clusters, cluster_n_triangles, cluster_area = mesh.cluster_connected_triangles()
    triangle_clusters = np.asarray(triangle_clusters)
    cluster_n_triangles = np.asarray(cluster_n_triangles)
    largest_cluster_idx = cluster_n_triangles.argmax()
    triangles_to_remove = triangle_clusters != largest_cluster_idx
    mesh.remove_triangles_by_mask(triangles_to_remove)

bbox = pcd.get_axis_aligned_bounding_box()
cropped_mesh = mesh.crop(bbox)

o3d.visualization.draw_geometries([cropped_mesh])
o3d.io.write_triangle_mesh(output, cropped_mesh)
