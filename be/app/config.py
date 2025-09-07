import os
from dotenv import load_dotenv

load_dotenv()
class Config: 
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/mydatabase')

SWAGGER_CONFIG = {
    "headers": [], 
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ], 
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs/"     
}

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Test API prediction and dashboard", 
        "description": "API for prediction and dashboard data",
        "version": "1.0.0"
    },
    "consumes": [
        "application/json"
    ],
    "produces": [
        "application/json"
    ],
}
  