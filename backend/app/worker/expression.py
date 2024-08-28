
import math

def get_geometry(feature):
    if 'geometry' in feature:
        return feature['geometry']
    return { 'type': '' }

def get_z(coordinates):
    if len(coordinates) == 3:
        return coordinates[2]
    return 0

def get_func(name, feature):
    if name in ['$maxZ', '$minZ']:
        geometry = get_geometry(feature)
        if geometry['type'] == 'Point':
            return get_z(geometry['coordinates'])
        if geometry['type'] == 'Polygon':
            min_z = math.inf
            max_z = -math.inf
            for ring in geometry['coordinates']:
                for coords in ring:
                    z = get_z(coords)
                    if z < min_z:
                        min_z = z
                    if z > max_z:
                        max_z = z
            if name == '$maxZ':
                return max_z
            return min_z
    return None

def parse_expression(type, value, feature, default_value = None):
    try:
        if not isinstance(value, list):
            if value == None:
                return None
            if type == 'string':
                return f"{value}"
            if type == 'number':
                return float(value)
            return value
        operator = value[0]

        _type = type
        if operator in ['property', 'func']:
            _type = ''

        value_length = len(value)

        a = None
        if value_length > 1:
            value_a = value[1]
            a = parse_expression(_type, value_a, feature)

        b = None
        if value_length > 2:
            value_b = value[2]
            b = parse_expression(_type, value_b, feature)

        if operator == '+':
            return float(a) + float(b)
        if operator == "-":
            return float(a) - float(b)
        if operator == "*":
            return float(a) * float(b)
        if operator == "/":
            return float(a) / float(b)
        if operator == "concat":
            return f"{a}{b}"
        if operator == "lowercase":
            return f"{a}".lower()
        if operator == "uppercase":
            return f"{a}".upper()
        if operator == "property":
            if a in feature['properties']:
                return feature['properties'][a]
        if operator == "func":
            return get_func(a, feature)
        return None
    except Exception as e:
        return default_value
