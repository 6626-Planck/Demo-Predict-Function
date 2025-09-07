from flask import Flask, jsonify
from flask_cors import CORS
from app.config import Config, SWAGGER_CONFIG, SWAGGER_TEMPLATE
from app.database import mongo
from flasgger import Swagger
from app.route import register_blueprints

def create_app(): 
    app = Flask(__name__)
    app.config.from_object(Config)

    mongo.init_app(app)
    CORS(app)

    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
    register_blueprints(app)
    
    return app