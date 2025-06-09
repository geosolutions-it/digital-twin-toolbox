import math
import numpy as np
from pyproj import Transformer

def reproject(coords, from_proj, to_proj):
    transformer = Transformer.from_proj(from_proj, to_proj)
    x, y, z = transformer.transform(
        coords[0], coords[1], coords[2] if len(coords) > 2 else 0.0
    )
    return [x, y, z]

def multiply_matrix(m1, m2):
    return np.array(m1).reshape(4, 4).dot(np.array(m2).reshape(4, 4)).flatten().tolist()

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

def rad(deg):
    return deg * math.pi / 180

def to_box(x, y, level, size):
    level_size = 2 ** level
    w_unit = size[0] / level_size
    h_unit = size[1] / level_size
    center_x = -(size[0] / 2) + (x * w_unit) + w_unit / 2
    center_y = (size[1] / 2) - (y * h_unit) - h_unit / 2
    return [
        center_x, center_y, 0,
        w_unit / 2, 0, 0,
        0, h_unit / 2, 0,
        0, 0, size[2] / 2
    ]

def run(config):

    size = config.get('size')
    depth = config.get('depth')
    offset = config.get('offset')
    center = config.get('center')
    coordinates = center.get('coordinates')
    crs = center.get('crs')

    if offset:
        coordinates[0] += offset[0]
        coordinates[1] += offset[1]
        coordinates[2] += offset[2] if len(offset) > 2 else 0
    
    diagonal = math.sqrt(size[0] ** 2 + size[1] ** 2)

    max_geometric_error = config.get('max_geometric_error', diagonal / 4)

    geometric_errors = []
    for level in range(depth + 1):
        geometric_errors.append(max_geometric_error / ((level + 1) ** 2))

    geometric_errors.append(0)

    coords = reproject([coordinates[0], coordinates[1]], crs, 'WGS84')
    latitude= coords[0]
    longitude = coords[1]
    z = coordinates[2]

    height = size[1]
    width = size[0]

    min_z = z - size[2] / 2
    max_z = z + size[2] / 2


    def region(bbox):
        minx, miny, maxx, maxy = bbox
        lb = reproject([minx, miny], crs, 'WGS84')
        rt = reproject([maxx, maxy], crs, 'WGS84')
        return [rad(lb[1]), rad(lb[0]), rad(rt[1]), rad(rt[0]), min_z, max_z]
    

    def quad(params):
        x = params['x']
        y = params['y']
        bbox = params.get('bbox')
        level = params['level']
        uri = params.get('uri')
        transform = params.get('transform')
        
        level_size = 2 ** level
        w_unit = width / level_size
        h_unit = height / level_size
        
        leaf = {
            'geometricError': geometric_errors[level + 1],
            'refine': 'REPLACE'
        }
        
        if bbox:
            leaf['boundingVolume'] = {
                'box': to_box(x, y, level, size)
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
            center_x = bbox[0] + next_w_unit
            center_y = bbox[1] + next_h_unit
            
            children = []
            quads = [
                {'bbox': [bbox[0], center_y, center_x, bbox[3]], 'x': x0, 'y': y0, 'level': next_level, 'uri': f'{next_level}_{y0}_{x0}.glb'},
                {'bbox': [center_x, center_y, bbox[2], bbox[3]], 'x': x1, 'y': y0, 'level': next_level, 'uri': f'{next_level}_{y0}_{x1}.glb'},
                {'bbox': [bbox[0], bbox[1], center_x, center_y], 'x': x0, 'y': y1, 'level': next_level, 'uri': f'{next_level}_{y1}_{x0}.glb'},
                {'bbox': [center_x, bbox[1], bbox[2], center_y], 'x': x1, 'y': y1, 'level': next_level, 'uri': f'{next_level}_{y1}_{x1}.glb'}
            ]
            
            for q in quads:
                children.extend([quad(q)])
                
            if transform:
                return {
                    'boundingVolume': {
                        'region': region(bbox),
                        'box': to_box(0, 0, 0, size)
                    },
                    'transform': transform,
                    'geometricError': geometric_errors[level],
                    'refine': 'REPLACE',
                    'children': [{'children': children, **leaf}]
                }
            return {**leaf, 'children': children}
            
        return leaf

    transform = get_transform({ 'scale': 1, 'latitude': latitude, 'longitude': longitude, 'altitude': z })

    tileset = {
        'asset': {
            'version': '1.1'
        },
        'root': quad({
            'x': 0,
            'y': 0,
            'bbox': [
                coordinates[0] - width / 2,
                coordinates[1] - height / 2,
                coordinates[0] + width / 2,
                coordinates[1] + height / 2
            ],
            'level': 0,
            'transform': transform,
            'uri': '0_0_0.glb'
        })
    }
    return tileset
