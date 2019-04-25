import logging

logging.basicConfig(
    format='%(asctime)s :: %(levelname)s :: [%(filename)s:%(lineno)d] :: %(message)s',
    level=logging.INFO
)

logger = logging.getLogger('geoapi')
