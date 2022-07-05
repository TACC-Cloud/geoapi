from shapely.geometry import shape
import shapely


def convert_3D_2D(shape) -> shape:
    def _to_2d(x, y, z=None):
        return tuple(filter(None, [x, y]))

    new_shape = shapely.ops.transform(_to_2d, shape)
    return new_shape
