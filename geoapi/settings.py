import os


class Config(object):
    DEBUG = False
    TESTING = False
    DB_USERNAME = 'dev'
    DB_NAME = 'dev'
    DB_PASSWD = 'dev'
    DB_HOST = 'postgres'
    ASSETS_BASE_DIR = os.environ.get('ASSETS_BASE_DIR', '/assets')
    JWT_PUB_KEY = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCMqntVjj71pXRRATmpF7QkN+TeK7bTI3eY/3F6X2ElM9oSwvT49LXSoWV5EifazQoD9IaeqpBQ33o1jlLNkYhLfhZBJsQQ6RT7kKEn44nh2w7SQOWT0CgJRT+18ISTqnbNtyjc1+Akv7EO0VlDRpHKwSV4mAgDcexOmtnpfCYVy34KtqA0zI6v4dgQCocgj/GqZsGpU0b+Wkn1btRut7kPPXzBsE3HMiU82AAJSyybT2uHErErQUkFoD79K1tquE0fY1Ce7rJX+vnlpDCA1UssnwlqRsrb/IIs8q2dAOrzHf/batMAwzbvadwGAzeH6qeK+G0ftbPHpQT4o8L7hBIVPi0t9EOaRDqz9WdORUTcFPbnGJo4ZqVRK0HzEPc767wCpeVpVGiJd4iaJF8TjYesk8+axzCAtdp045qdqv9W0ZOoc0ev//6U9UANgtPHAbPrC7XMq5n9b1wC+G4fLfhg8WpDAcA9PeNKsB6GfEvL2zS1sNaG0VVIq9HuR98xvbXdyN5fSnKb7oau7RKalHCVZijPUNlkpUpBen96kQaXwLW0s5ih9liBAfFZERO4cgVHm6dcx3y0BDmFWyFXktfu2Om0NyuAoBEetRlxOQEyYS5mc1egsyVeFb/jAb1zdLMRFuZXv72j+f9h082R9VymfP7gO15lKb+k8tvMCncfBw=='
    RABBITMQ_USERNAME = 'dev'
    RABBITMQ_PASSWD = 'dev'
    RABBITMQ_VHOST = 'dev'
    RABBITMQ_HOSTNAME = 'rabbitmq'


class ProductionConfig(Config):
    DEBUG = False
    DB_USERNAME = os.environ.get("DB_USERNAME")
    DB_NAME = os.environ.get("DB_NAME")
    DB_PASSWD = os.environ.get("DB_PASSWD")
    DB_HOST = os.environ.get("DB_HOST")
    JWT_PUB_KEY = os.environ.get("JWT_PUB_KEY")
    RABBITMQ_USERNAME = os.environ.get("RABBITMQ_USERNAME")
    RABBITMQ_PASSWD = os.environ.get("RABBITMQ_PASSWD")
    RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST")
    RABBITMQ_HOSTNAME = os.environ.get("RABBITMQ_HOSTNAME")


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
if APP_ENV == 'production':
    settings = ProductionConfig
elif APP_ENV == 'testing':
    settings = TestingConfig
else:
    settings = DevelopmentConfig
