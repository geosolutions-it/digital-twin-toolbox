import math

RADIANS_PER_DEGREE = math.pi / 180.0

RADII_SQUARED = [
  6378137.0 * 6378137.0,
  6378137.0 * 6378137.0,
  6356752.3142451793 * 6356752.3142451793,
]

def to_radians(degrees):
    return degrees * RADIANS_PER_DEGREE

def vector_length(vector):
    x = vector[0]
    y = vector[1]
    z = vector[2]
    return x * x + y * y + z * z

def vector_multiply_scalar(vector, scalar):
    x = vector[0]
    y = vector[1]
    z = vector[2]
    return [x * scalar, y * scalar, z * scalar]

def vector_divide_scalar(vector, scalar):
    return vector_multiply_scalar(vector, 1 / scalar)

def vector_normalize(vector):
    return vector_divide_scalar(vector, vector_length(vector))

def vector_add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]

def vector_multiply(a, b):
    return [a[0] * b[0], a[1] * b[1], a[2] * b[2]]

def vector_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def from_radians(longitude, latitude, height):
    cos_latitude = math.cos(latitude)
    x = cos_latitude * math.cos(longitude)
    y = cos_latitude * math.sin(longitude)
    z = math.sin(latitude)

    normalized = vector_normalize([x, y, z])
    k = vector_multiply(RADII_SQUARED, normalized)
    gamma = math.sqrt(vector_dot(normalized, k))

    output = vector_add(
        vector_divide_scalar(k, gamma),
        vector_multiply_scalar(normalized, height)
    )
    return output

def convert_to_cartesian(coords):
    longitude = coords[0]
    latitude = coords[1]
    height = coords[2]
    if not height:
        height = 0
    return from_radians(to_radians(longitude), to_radians(latitude), height)
