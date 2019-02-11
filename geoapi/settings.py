import os

class Config(object):
    DEBUG = False
    TESTING = False
    DB_USERNAME = 'dev'
    DB_NAME = 'dev'
    DB_PASSWD = 'dev'
    ASSETS_BASE_DIR = '/tmp'

class ProductionConfig(Config):
    DATABASE_URI = 'mysql://user@localhost/foo'

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
