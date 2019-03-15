import os

class Config(object):
    DEBUG = False
    TESTING = False
    DB_USERNAME = 'dev'
    DB_NAME = 'dev'
    DB_PASSWD = 'dev'
    DB_HOST = 'postgres'
    ASSETS_BASE_DIR = os.environ.get('ASSETS_BASE_DIR', '/assets')
    JWT_SECRET_KEY = 'your-256-bit-secret'


class ProductionConfig(Config):
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    DB_USERNAME = 'dev'
    DB_NAME = 'test'
    DB_PASSWD = 'dev'
    DB_HOST = 'localhost'
    TESTING = True
    ASSETS_BASE_DIR = '/tmp'


APP_ENV = os.environ.get('APP_ENV', '').lower()
if APP_ENV == 'prod':
    settings = ProductionConfig
elif APP_ENV == 'testing':
    settings = TestingConfig
else:
    settings = DevelopmentConfig
