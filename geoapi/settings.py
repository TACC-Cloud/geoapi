import os


class Config(object):
    DEBUG = False
    TESTING = False
    DB_USERNAME = 'dev'
    DB_NAME = 'dev'
    DB_PASSWD = 'dev'
    DB_HOST = 'postgres'
    ASSETS_BASE_DIR = os.environ.get('ASSETS_BASE_DIR', '/assets')
    JWT_PUB_KEY = 'MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAjKp7VY4-9aV0UQE5qRe0JDfk3iu20yN3mP9xel9hJTPaEsL0-PS10qFleRIn2s0KA_SGnqqQUN96NY5SzZGIS34WQSbEEOkU-5ChJ-OJ4dsO0kDlk9AoCUU_tfCEk6p2zbco3NfgJL-xDtFZQ0aRysEleJgIA3HsTprZ6XwmFct-CragNMyOr-HYEAqHII_xqmbBqVNG_lpJ9W7Ubre5Dz18wbBNxzIlPNgACUssm09rhxKxK0FJBaA-_StbarhNH2NQnu6yV_r55aQwgNVLLJ8JakbK2_yCLPKtnQDq8x3_22rTAMM272ncBgM3h-qnivhtH7Wzx6UE-KPC-4QSFT4tLfRDmkQ6s_VnTkVE3BT25xiaOGalUStB8xD3O-u8AqXlaVRoiXeImiRfE42HrJPPmscwgLXadOOanar_VtGTqHNHr__-lPVADYLTxwGz6wu1zKuZ_W9cAvhuHy34YPFqQwHAPT3jSrAehnxLy9s0tbDWhtFVSKvR7kffMb213cjeX0pym-6Gru0SmpRwlWYoz1DZZKVKQXp_epEGl8C1tLOYofZYgQHxWRETuHIFR5unXMd8tAQ5hVshV5LX7tjptDcrgKARHrUZcTkBMmEuZnNXoLMlXhW_4wG9c3SzERbmV7-9o_n_YdPNkfVcpnz-4DteZSm_pPLbzAp3HwcCAwEAAQ'
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
