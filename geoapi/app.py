
from flask import Flask
from geoapi.routes import api
from geoapi.settings import settings as app_settings

app = Flask(__name__)
api.init_app(app)
app.config.from_object(app_settings)
