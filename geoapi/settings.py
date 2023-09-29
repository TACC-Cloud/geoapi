import os


class Config(object):
    DEBUG = False
    TESTING = False
    ASSETS_BASE_DIR = os.environ.get('ASSETS_BASE_DIR', '/assets')
    JWT_PUB_KEY = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCUp/oV1vWc8/TkQSiAvTousMzOM4asB2iltr2QKozni5aVFu818MpOLZIr8LMnTzWllJvvaA5RAAdpbECb+48FjbBe0hseUdN5HpwvnH/DW8ZccGvk53I6Orq7hLCv1ZHtuOCokghz/ATrhyPq+QktMfXnRS4HrKGJTzxaCcU7OQIDAQAB'  # noqa: E501
    RESTPLUS_MASK_SWAGGER = False
    TENANT = os.environ.get("TENANT")
    STREETVIEW_DIR = os.environ.get('STREETVIEW_DIR', '/assets/streetview')


class DeployedConfig(Config):
    DEBUG = False
    DB_USERNAME = os.environ.get("DB_USERNAME")
    DB_NAME = os.environ.get("DB_NAME")
    DB_PASSWD = os.environ.get("DB_PASSWD")
    DB_HOST = os.environ.get("DB_HOST")
    RABBITMQ_USERNAME = os.environ.get("RABBITMQ_USERNAME")
    RABBITMQ_PASSWD = os.environ.get("RABBITMQ_PASSWD")
    RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST")
    RABBITMQ_HOSTNAME = os.environ.get("RABBITMQ_HOSTNAME")
    MAPILLARY_CLIENT_ID = os.environ.get('MAPILLARY_CLIENT_ID', 'MLY|5156692464392931|4f1118aa1b06f051a44217cb56bedf79')


class LocalDevelopmentConfig(Config):
    DEBUG = True
    PROPAGATE_EXCEPTIONS = False
    RABBITMQ_USERNAME = 'dev'
    RABBITMQ_PASSWD = 'dev'
    RABBITMQ_VHOST = 'dev'
    RABBITMQ_HOSTNAME = 'rabbitmq'
    DB_USERNAME = 'dev'
    DB_NAME = 'dev'
    DB_PASSWD = 'dev'
    DB_HOST = 'postgres'
    MAPILLARY_CLIENT_ID = os.environ.get('MAPILLARY_CLIENT_ID', 'MLY|4866220476802272|cedfb10deac752ca3ddf83997cef60a4')


class UnitTestingConfig(LocalDevelopmentConfig):
    DB_NAME = 'test'
    DB_HOST = os.environ.get('DB_HOST', 'postgres')
    TESTING = True
    STREETVIEW_DIR = os.environ.get('STREETVIEW_DIR', '/tmp/streetview')
    ASSETS_BASE_DIR = '/tmp'
    TENANT = "{\"DESIGNSAFE\": {\"service_account_token\": \"ABCDEFG12344\"}," \
             " \"TEST\": {\"service_account_token\": \"ABCDEFG12344\"}  }"


APP_ENV = os.environ.get('APP_ENV', '').lower()
if APP_ENV == 'production' or APP_ENV == 'staging' or APP_ENV == 'dev':
    settings = DeployedConfig
elif APP_ENV == 'testing':
    settings = UnitTestingConfig
else:
    settings = LocalDevelopmentConfig
