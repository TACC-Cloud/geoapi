import os


class Config(object):
    # Flask settings
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get("FLASK_SESSION_SECRET_KEY")

    # Flask-RESTPlus settings
    RESTPLUS_MASK_SWAGGER = False

    # Tapis-related settings
    TAPIS_PUB_KEY_FOR_VALIDATION = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmqQ9Je2o5zydpVY865qao1iX1+E1Kxw3Hpb8FX3PHGjDoOAxrpY2lV0jdXwEPECbYbTv51fu7wBh8p6Y5outup+aRUfAAJxvq0D0w//AQTNE7bYbVNSGlVt68vnywMoFOab2zZ6o83jrlhmvkswb7N48aaZTnY0tCAYJ7SCCj2BN7BsbBoB4Bzv62S86Sw0hMXf3mJlWMoh5bDRANVYbOJ31bzIzJFxCs0hyfLBT8X+d2qSxfF7i33JOIDzOW0GiI0McVJZpifnSbGnLcw/mBGlNB67zwZ9PTsi2TS3s8z0TwnmP9ORM/cpqEfu4yFPvWeADsVAE9h9ZZX6nRCQ91QIDAQAB"  # noqa: E501
    TAPIS_CLIENT_ID = os.environ.get("TAPIS_CLIENT_ID")
    TAPIS_CLIENT_KEY = os.environ.get("TAPIS_CLIENT_KEY")

    # TODO Remove see https://tacc-main.atlassian.net/browse/WG-513
    TMP_TAPIS_CLIENT_ID = os.environ.get("TMP_TAPIS_CLIENT_ID")
    TMP_TAPIS_CLIENT_KEY = os.environ.get("TMP_TAPIS_CLIENT_KEY")

    # Mapillary-related settings
    MAPILLARY_CLIENT_ID = os.environ.get("MAPILLARY_CLIENT_ID")
    MAPILLARY_CLIENT_SECRET = os.environ.get("MAPILLARY_CLIENT_SECRET")
    MAPILLARY_CLIENT_TOKEN = os.environ.get("MAPILLARY_CLIENT_TOKEN")
    MAPILLARY_AUTH_URL = "https://www.mapillary.com/connect"
    MAPILLARY_API_URL = "https://graph.mapillary.com"
    MAPILLARY_SCOPE = "user:email+user:read+user:write+public:write+public:upload+private:read+private:write+private:upload"

    # Other settings
    ASSETS_BASE_DIR = os.environ.get("ASSETS_BASE_DIR", "/assets")
    TENANT = os.environ.get("TENANT")
    STREETVIEW_DIR = os.environ.get("STREETVIEW_DIR", "/assets/streetview")
    DESIGNSAFE_URL = os.environ.get("DESIGNSAFE_URL")
    APP_ENV = os.environ.get("APP_ENV")


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
    MAPILLARY_CLIENT_ID = os.environ.get(
        "MAPILLARY_CLIENT_ID", "MLY|5156692464392931|4f1118aa1b06f051a44217cb56bedf79"
    )


class LocalDevelopmentConfig(Config):
    DEBUG = True
    PROPAGATE_EXCEPTIONS = False
    RABBITMQ_USERNAME = "dev"
    RABBITMQ_PASSWD = "dev"
    RABBITMQ_VHOST = "dev"
    RABBITMQ_HOSTNAME = "rabbitmq"
    DB_USERNAME = "dev"
    DB_NAME = "dev"
    DB_PASSWD = "dev"
    DB_HOST = "postgres"


class UnitTestingConfig(LocalDevelopmentConfig):
    DB_NAME = "test"
    DB_HOST = os.environ.get("DB_HOST", "postgres")
    TESTING = True
    STREETVIEW_DIR = os.environ.get("STREETVIEW_DIR", "/tmp/streetview")
    ASSETS_BASE_DIR = "/tmp"
    DESIGNSAFE_URL = os.environ.get(
        "DESIGNSAFE_URL", "https://designsafe-not-real.tacc.utexas.edu"
    )
    TAPIS_CLIENT_ID = "test_client_id"
    TAPIS_CLIENT_KEY = "test_client_key_1234"
    SECRET_KEY = os.environ.get(
        "FLASK_SESSION_SECRET_KEY", "flask_session_secret_key_1234"
    )


APP_ENV = os.environ.get("APP_ENV", "").lower()
if APP_ENV == "production" or APP_ENV == "staging" or APP_ENV == "dev":
    settings = DeployedConfig
elif APP_ENV == "testing":
    settings = UnitTestingConfig
elif APP_ENV == "local":
    settings = LocalDevelopmentConfig
else:
    raise Exception("APP_ENV is not defined")
