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
    DB_USERNAME = os.environ.get("DB_USERNAME")
    DB_NAME = os.environ.get("DB_NAME")
    DB_PASSWD = os.environ.get("DB_PASSWD")
    DB_HOST = os.environ.get("DB_HOST")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")

class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    DB_USERNAME = 'dev'
    DB_NAME = 'test'
    DB_PASSWD = 'dev'
    DB_HOST = os.environ.get('DB_HOST', 'postgres')
    TESTING = True
    ASSETS_BASE_DIR = '/tmp'


APP_ENV = os.environ.get('APP_ENV', '').lower()
if APP_ENV == 'prod':
    settings = ProductionConfig
elif APP_ENV == 'testing':
    settings = TestingConfig
else:
    settings = DevelopmentConfig
