from flask import Blueprint 
from .routes import water_meter_bp, data_init_bp, prediction_bp

main_bp = Blueprint('main', __name__)

def register_blueprints(app):
    app.register_blueprint(water_meter_bp, url_prefix='/api/water-meters')
    app.register_blueprint(prediction_bp, url_prefix='/api/predictions')
    app.register_blueprint(data_init_bp, url_prefix='/api/data-init')