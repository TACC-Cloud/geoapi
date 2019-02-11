
from flask import Flask
from .routes import api

app = Flask(__name__)
api.init_app(app)
app.config.from_object('geoapi.settings.DevelopmentConfig')
