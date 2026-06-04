import math
import numpy as np
from pyproj import Transformer
from mathutils import Matrix
import os
import json

def reproject(coords, from_proj, to_proj):
    transformer = Transformer.from_proj(from_proj, to_proj)
    x, y, z = transformer.transform(
        coords[0], coords[1], coords[2] if len(coords) > 2 else 0.0
    )
    return [x, y, z]

def multiply_matrix(m1, m2):
    return np.array(m1).reshape(4, 4).dot(np.array(m2).reshape(4, 4)).flatten().tolist()

def get_location_and_rotation(params):
    s = params['scale']
    lat = params['latitude'] * math.pi / 180
    lon = params['longitude'] * math.pi / 180
    alt = params['altitude']

    a = 6378137.0 / s
    b = 6356752.3142 / s
    f = (a - b) / a

    e_sq = 2 * f - f * f

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)

    nu = a / math.sqrt(1 - e_sq * sin_lat * sin_lat)

    x = (nu + alt) * cos_lat * cos_lon
    y = (nu + alt) * cos_lat * sin_lon
    z = (nu * (1 - e_sq) + alt) * sin_lat

    xr = -sin_lon
    yr = cos_lon
    zr = 0

    xe = -cos_lon * sin_lat
    ye = -sin_lon * sin_lat
    ze = cos_lat

    xs = cos_lat * cos_lon
    ys = cos_lat * sin_lon
    zs = sin_lat

    return {
        'location': [x, y, z],
        'rotation': Matrix((
            (xr, xe, xs, 0),
            (yr, ye, ys, 0),
            (zr, ze, zs, 0),
            (0, 0, 0, 1)
        ))
    }

def get_transform(params):
    s = params['scale']
    lat = params['latitude'] * math.pi / 180
    lon = params['longitude'] * math.pi / 180
    alt = params['altitude']

    a = 6378137.0 / s
    b = 6356752.3142 / s
    f = (a - b) / a

    e_sq = 2 * f - f * f

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)

    nu = a / math.sqrt(1 - e_sq * sin_lat * sin_lat)

    x = (nu + alt) * cos_lat * cos_lon
    y = (nu + alt) * cos_lat * sin_lon
    z = (nu * (1 - e_sq) + alt) * sin_lat

    xr = -sin_lon
    yr = cos_lon
    zr = 0

    xe = -cos_lon * sin_lat
    ye = -sin_lon * sin_lat
    ze = cos_lat

    xs = cos_lat * cos_lon
    ys = cos_lat * sin_lon
    zs = sin_lat

    res = [
        xr, xe, xs, x,
        yr, ye, ys, y,
        zr, ze, zs, z,
        0, 0, 0, 1
    ]

    rot = [
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1
    ]

    mult = multiply_matrix(res, rot)

    scale_matrix = [
        s, 0, 0, 0,
        0, s, 0, 0,
        0, 0, s, 0,
        0, 0, 0, 1
    ]

    column_major_order = np.array(mult).reshape(4, 4).T.flatten().tolist()

    return multiply_matrix(column_major_order, scale_matrix)

def multiply_by_point(matrix, cartesian):

  vX = cartesian[0]
  vY = cartesian[1]
  vZ = cartesian[2]

  x = matrix[0] * vX + matrix[4] * vY + matrix[8] * vZ + matrix[12]
  y = matrix[1] * vX + matrix[5] * vY + matrix[9] * vZ + matrix[13]
  z = matrix[2] * vX + matrix[6] * vY + matrix[10] * vZ + matrix[14]

  return [x, y, z]

# from https://github.com/CesiumGS/3d-tiles-tools/blob/7287a32c35dbf6e5828b2a324dd20875aa2681d8/src/tools/tilesetProcessing/BoundingVolumes.ts#L172-L187
def transform_bounding_volume_box(bounding_volume_box, transform):
    center = [bounding_volume_box[0], bounding_volume_box[1], bounding_volume_box[2]]
    new_center = multiply_by_point(transform, center)
    rotation_scale = np.array([
        transform[0], transform[4], transform[8],
        transform[1], transform[5], transform[9],
        transform[2], transform[6], transform[10]
    ]).reshape(3, 3)
    half_axes = np.array([
        bounding_volume_box[3], bounding_volume_box[6], bounding_volume_box[9],
        bounding_volume_box[4], bounding_volume_box[7], bounding_volume_box[10],
        bounding_volume_box[5], bounding_volume_box[8], bounding_volume_box[11]
    ]).reshape(3, 3)
    new_half_axes = rotation_scale @ half_axes
    new_half_axes_list = new_half_axes.T.flatten().tolist()
    return [
        new_center[0], new_center[1], new_center[2],
        new_half_axes_list[0], new_half_axes_list[1], new_half_axes_list[2],
        new_half_axes_list[3], new_half_axes_list[4], new_half_axes_list[5],
        new_half_axes_list[6], new_half_axes_list[7], new_half_axes_list[8]
    ]

def rad(deg):
    return deg * math.pi / 180

def to_box(info):
    size = info.get('size')
    center = info.get('center')
    return transform_bounding_volume_box([
        center[0], center[1], center[2],
        size[0] / 2, 0, 0,
        0, size[1] / 2, 0,
        0, 0, size[2] / 2
    ], info.get('transform'))

def run(config):

    size = config.get('size')
    depth = config.get('depth')
    output_dir = config.get('output_dir')

    diagonal = math.sqrt(size[0] ** 2 + size[1] ** 2 + size[2] ** 2) 

    max_geometric_error = config.get('max_geometric_error', diagonal / 3)

    geometric_errors = []
    for level in range(depth + 1):
        geometric_errors.append(max_geometric_error / (2 ** (level + 1)))

    geometric_errors.append(0)

    height = size[1]
    width = size[0]

    def quad(params):
        x = params['x']
        y = params['y']
        info = params.get('info')
        level = params['level']
        uri = params.get('uri')
        root = params.get('root', False)
        
        level_size = 2 ** level
        w_unit = width / level_size
        h_unit = height / level_size
        
        leaf = {
            'geometricError': geometric_errors[level + 1],
            'refine': 'REPLACE'
        }
        
        if info:
            leaf['boundingVolume'] = {
                'box': to_box(info)
            }
        if uri:
            leaf['content'] = {'uri': uri}
            
        if level < depth:
            next_level = level + 1
            next_size = 2 ** next_level
            next_w_unit = width / next_size
            next_h_unit = height / next_size
            translate_x = (x * w_unit)
            translate_y = (y * h_unit)
            x0 = round(translate_x / next_w_unit)
            x1 = x0 + 1
            y0 = round(translate_y / next_h_unit)
            y1 = y0 + 1

            children = []

            quads = [
                {'x': x0, 'y': y0, 'level': next_level, 'uri': f'{next_level}_{y0}_{x0}.glb', 'info_path': f'{next_level}_{y0}_{x0}.json'},
                {'x': x1, 'y': y0, 'level': next_level, 'uri': f'{next_level}_{y0}_{x1}.glb', 'info_path': f'{next_level}_{y0}_{x1}.json'},
                {'x': x0, 'y': y1, 'level': next_level, 'uri': f'{next_level}_{y1}_{x0}.glb', 'info_path': f'{next_level}_{y1}_{x0}.json'},
                {'x': x1, 'y': y1, 'level': next_level, 'uri': f'{next_level}_{y1}_{x1}.glb', 'info_path': f'{next_level}_{y1}_{x1}.json'}
            ]

            for q in quads:
                info_path = os.path.join(output_dir, q.get('info_path'))
                if os.path.exists(info_path):
                    with open(info_path) as f:
                        q['info'] = json.load(f)
                    children.extend([quad(q)])

            if root:
                root_level = {
                    'geometricError': geometric_errors[level],
                    'refine': 'REPLACE',
                    'children': [{'children': children, **leaf}]
                }
                if info:
                    root_level['boundingVolume'] = {
                        'box': to_box(info)
                    }
                return root_level
            return {**leaf, 'children': children}
            
        return leaf

    info_path = os.path.join(output_dir, '0_0_0.json')

    info = None
    if os.path.exists(info_path):
        with open(info_path) as f:
            info = json.load(f)

    tileset = {
        'asset': {
            'version': '1.1'
        },
        'root': quad({
            'x': 0,
            'y': 0,
            'info': info,
            'level': 0,
            'root': True,
            'uri': '0_0_0.glb'
        })
    }
    return tileset
