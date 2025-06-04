import os
import json
import math
import numpy as np
from pyproj import Transformer

file = {
    "name": "output"  
}

config = {
    "zOffset": 0,
    "geometricErrors": "200,100,20,5,0",
    "crs": "EPSG:7791"
}

def cs2cs(coords, from_proj, to_proj):
    transformer = Transformer.from_proj(from_proj, to_proj, always_xy=True)
    x, y, z = transformer.transform(
        coords[0], coords[1], coords[2] if len(coords) > 2 else 0.0
    )
    return [x, y, z]

def check_uri(output_dir, leaf):
    if os.path.exists(os.path.join(output_dir, leaf['uri'])):
        return [leaf]
    return []

def multiply_matrix(m1, m2):
    return np.array(m1).reshape(4, 4).dot(np.array(m2).reshape(4, 4)).flatten().tolist()

def convert_to_column_major_order(m):
    return np.array(m).reshape(4, 4).T.flatten().tolist()

def to_ecef_transform(params):
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

    return multiply_matrix(convert_to_column_major_order(mult), scale_matrix)

def rad(deg):
    return deg * math.pi / 180

def create_tileset(file, config):
    output_dir = f"{file['name']}/"
    
    if not os.path.exists(os.path.join(output_dir, "info.json")):
        raise FileNotFoundError(f"{output_dir}info.json not available")
    
    with open(os.path.join(output_dir, "info.json"), 'r') as f:
        info = json.load(f)
    
    size = info.get('size')
    depth = info.get('depth')
    center_offset = info.get('center')

    lat0, lon0, alt0 = 43.7742375737494, 11.258511650022717, 0

    center = cs2cs([lat0, lon0, alt0], 'WGS84', config.get('crs', 'EPSG:7791'))
    if center_offset:
        center[0] += center_offset[0]
        center[1] += center_offset[1]
        center[2] += center_offset[2] if len(center_offset) > 2 else 0
    
    z_offset = config.get('zOffset', 0)
    geometric_errors_config = config.get('geometricErrors', '200,100,20,5,0')
    crs = config.get('crs', 'EPSG:7791')
    geometric_errors = [float(x) for x in geometric_errors_config.split(',')]
    coords = cs2cs([center[0], center[1]], crs, 'WGS84')
    latitude= coords[1]
    longitude = coords[0]
    z = center[2] + z_offset
    size_ = size
    height = size_[1]
    width = size_[0]

    min_z = z - size[2] / 2
    max_z = z + size[2] / 2


    def region(bbox):
        minx, miny, maxx, maxy = bbox
        lb = cs2cs([minx, miny], crs, 'WGS84')
        rt = cs2cs([maxx, maxy], crs, 'WGS84')
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
            leaf['boundingVolume'] = {'region': region(bbox)}
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
                children.extend([quad(child) for child in check_uri(output_dir, q)])
                
            if transform:
                return {
                    'boundingVolume': {'region': region(bbox)} if bbox else None,
                    'transform': transform,
                    'geometricError': geometric_errors[level],
                    'refine': 'REPLACE',
                    'children': [{'children': children, **leaf}]
                }
            return {**leaf, 'children': children}
            
        return leaf

    print(latitude, longitude, z ,"values for ecef")
    transform = to_ecef_transform({'scale': 1, 'latitude': latitude, 'longitude': longitude, 'altitude': z})
    tileset = {
        'asset': {
            'version': '1.1'
        },
        'root': quad({
            'x': 0,
            'y': 0,
            'bbox': [
                center[0] - width / 2,
                center[1] - height / 2,
                center[0] + width / 2,
                center[1] + height / 2
            ],
            'level': 0,
            'transform': transform,
            'uri': '0_0_0.glb'
        })
    }
    with open(os.path.join(output_dir, 'tileset.json'), 'w') as f:
        json.dump(tileset, f)
    
    print(f"Tileset created successfully at {output_dir}tileset.json")
    return tileset

if __name__ == "__main__":
    try:
        create_tileset(file, config)
    except Exception as e:
        print(f"Error creating tileset: {e}")
