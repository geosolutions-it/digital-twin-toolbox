
import sqlalchemy.types as types
from sqlalchemy import func
import json
from decimal import Decimal
from datetime import date, datetime

class GeometryType(types.UserDefinedType):
    cache_ok = True

    def __init__(self, geometry_type = "POLYHEDRALSURFACEZ", epsg_code = 4326):
        self.geometry_type = geometry_type
        self.epsg_code = epsg_code

    def get_col_spec(self, **kw):
        return f"geometry({self.geometry_type}, {self.epsg_code})"
    
    def bind_expression(self, bindvalue):
        return func.ST_GeomFromText(bindvalue, type_=self)

    def column_expression(self, col):
        return func.ST_AsText(col, type_=self)

    def bind_processor(self, dialect):
        def process(value):
            return value
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            return value
        return process

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)