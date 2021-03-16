import os


class Config(object):
    DEBUG = False
    TESTING = False
    DB_USERNAME = 'dev'
    DB_NAME = 'dev'
    DB_PASSWD = 'dev'
    DB_HOST = 'postgres'
    ASSETS_BASE_DIR = os.environ.get('ASSETS_BASE_DIR', '/assets')
    JWT_PUB_KEY = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCUp/oV1vWc8/TkQSiAvTousMzOM4asB2iltr2QKozni5aVFu818MpOLZIr8LMnTzWllJvvaA5RAAdpbECb+48FjbBe0hseUdN5HpwvnH/DW8ZccGvk53I6Orq7hLCv1ZHtuOCokghz/ATrhyPq+QktMfXnRS4HrKGJTzxaCcU7OQIDAQAB'
    RABBITMQ_USERNAME = 'dev'
    RABBITMQ_PASSWD = 'dev'
    RABBITMQ_VHOST = 'dev'
    RABBITMQ_HOSTNAME = 'rabbitmq'
    RESTPLUS_MASK_SWAGGER = False
    TENANT = os.environ.get("TENANT")
    STREETVIEW_DIR = os.environ.get('STREETVIEW_DIR', '/assets/streetview')

class ProductionConfig(Config):
    DEBUG = False
    DB_USERNAME = os.environ.get("DB_USERNAME")
    DB_NAME = os.environ.get("DB_NAME")
    DB_PASSWD = os.environ.get("DB_PASSWD")
    DB_HOST = os.environ.get("DB_HOST")
    RABBITMQ_USERNAME = os.environ.get("RABBITMQ_USERNAME")
    RABBITMQ_PASSWD = os.environ.get("RABBITMQ_PASSWD")
    RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST")
    RABBITMQ_HOSTNAME = os.environ.get("RABBITMQ_HOSTNAME")


class DevelopmentConfig(Config):
    DEBUG = True
    PROPAGATE_EXCEPTIONS = False

class TestingConfig(Config):
    DB_USERNAME = 'dev'
    DB_NAME = 'test'
    DB_PASSWD = 'dev'
    DB_HOST = os.environ.get('DB_HOST', 'postgres')
    TESTING = True
    ASSETS_BASE_DIR = '/tmp'
    TENANT = "{\"DESIGNSAFE\": {\"service_account_token\": \"ABCDEFG12344\"} }"


APP_ENV = os.environ.get('APP_ENV', '').lower()
if APP_ENV == 'production':
    settings = ProductionConfig
elif APP_ENV == 'testing':
    settings = TestingConfig
else:
    settings = DevelopmentConfig
