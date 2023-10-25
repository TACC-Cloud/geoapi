from pathlib import Path

GEOJSON_FILE_EXTENSIONS = (
    'json', 'geojson'
)

IMAGE_FILE_EXTENSIONS = (
    'jpeg', 'jpg',
)

VIDEO_FILE_EXTENSIONS = (
    'mp4', 'mov', 'mpeg4', 'webm'
)

# TODO not used; remove from code base
AUDIO_FILE_EXTENSIONS = (
    'mp3', 'aac'
)

GPX_FILE_EXTENSIONS = (
    'gpx',
)

SHAPEFILE_FILE_EXTENSIONS = (
    'shp',
)

RAPP_QUESTIONNAIRE_FILE_EXTENSIONS = (
    'rq',
)

RAPP_QUESTIONNAIRE_ARCHIVE_EXTENSIONS = 'rqa'

ALLOWED_GEOSPATIAL_FEATURE_ASSET_EXTENSIONS = IMAGE_FILE_EXTENSIONS + VIDEO_FILE_EXTENSIONS

INI_FILE_EXTENSIONS = (
    'ini',
)

# Files who can be directly imported (with or without Tapis metadata)
ALLOWED_GEOSPATIAL_EXTENSIONS_FOR_SCRAPING = IMAGE_FILE_EXTENSIONS + GPX_FILE_EXTENSIONS + GEOJSON_FILE_EXTENSIONS +\
    SHAPEFILE_FILE_EXTENSIONS + RAPP_QUESTIONNAIRE_FILE_EXTENSIONS


def is_member_of_rapp_project_folder(path):
    """
    Check to see if path is contained within RApp project folder
    :param path: str
    """
    return "/RApp/" in path


def is_member_of_rqa_folder(path):
    """
    Check to see if path is contained within RApp project folder
    :param path: str
    """
    path_obj = Path(path)
    return path_obj.parent and path_obj.parent.name.endswith('.' + RAPP_QUESTIONNAIRE_ARCHIVE_EXTENSIONS)


def is_file_supported_for_automatic_scraping(path):
    """
    Check to see if file has a type supported for automatic importing
    :param path: str
    """
    path_obj = Path(path)
    suffix = path_obj.suffix.lower().lstrip('.')
    return (suffix in ALLOWED_GEOSPATIAL_EXTENSIONS_FOR_SCRAPING or  # supported files (with or without Tapis metadata)
            suffix in ALLOWED_GEOSPATIAL_FEATURE_ASSET_EXTENSIONS)  # with metadata (i.e. within /Rapp folder)


def is_supported_for_automatic_scraping_without_metadata(path):
    """
    Check to see if file is supported for automatic importing (without metadata).

    Note: assets like images inside the questionnaire archive (i.e in .rqa) should be ignored. Only the
    .rq file inside a .rqa file should be imported.

    :param path: str
    """
    path_obj = Path(path)
    file_suffix = path_obj.suffix.lower().lstrip('.')
    return (file_suffix in ALLOWED_GEOSPATIAL_EXTENSIONS_FOR_SCRAPING and
            (not is_member_of_rqa_folder(path) or file_suffix in RAPP_QUESTIONNAIRE_FILE_EXTENSIONS))  # if in .rqa, then only .rq file


def is_supported_file_type_in_rapp_folder_and_needs_metadata(path):
    """
    Check if file is in /Rapp folder and is importable and if Tapis metadata service should be used to derive
    the file's geolocation

    This applies to image and video files (i.e. ALLOWED_GEOSPATIAL_FEATURE_ASSET_EXTENSIONS) in the RApp project folder
    but the exception is the image and video files within the .rqa folder.

    :param path: str
    """
    path_obj = Path(path)
    return (is_member_of_rapp_project_folder(path)
            and path_obj.suffix.lower().lstrip('.') in ALLOWED_GEOSPATIAL_FEATURE_ASSET_EXTENSIONS
            and not is_member_of_rqa_folder(path))
