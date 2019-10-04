from geojson import Point, Polygon, Feature
import laspy

def get_geojson_feature(lidar_file):
    """ Get geojson feature

    :param str lidar_file: lidar file path
    :return: polygon feature
    :rtype: geojson.Feature
    :raises ValueError: if the message_body exceeds 160 characters
    :raises TypeError: if the message_body is not a basestring
    """
    # build with entwine
    entwine.build(lidar_file, entwine_output_dir)

    # grab bounds of scan
    bounding_points = entwine.get_bounding_info(entwine_output_dir)

    # save a FeatureAsset
    polygon = Polygon([[Point(bounding_points[0]),
                      Point((bounding_points[1][0], bounding_points[0][1])),
                      bounding_points[1],
                      Point((bounding_points[0][0], bounding_points[1][1])),
                        Point(bounding_points[0])]])
    feature = Feature(geometry=polygon,
                      properties={"point_cloud_file": lidar_file})
    return feature