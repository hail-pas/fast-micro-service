from pypika_tortoise import CustomFunction
from tortoise.expressions import Function


class STAsWKBFunc(Function):
    """
    from shapely import wkb
    from shapely.geometry import mapping


    geo_data_binary = f.geo_data_wkb
    geom = wkb.loads(geo_data_binary)
    geojson = mapping(geom)

    """

    database_func = CustomFunction(
        "ST_AsWKB",
        [
            "name",
        ],
    )


class Md5Func(Function):
    """
    md5
    """

    database_func = CustomFunction(
        "md5",
        [
            "field",
        ],
    )
