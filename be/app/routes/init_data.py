from flask import Blueprint, jsonify
from app.database import mongo
import csv
import os
from datetime import datetime
import pandas as pd
from flasgger import swag_from

data_init_bp = Blueprint('data_init', __name__)

@data_init_bp.route('/init_data', methods=['POST']) 
@swag_from({
    'tags': ['Data Initialization'],
    'responses': {
        200: {
            'description': 'Data initialized successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'results': {
                        'type': 'object',
                        'additionalProperties': {'type': 'integer'}
                    }
                }
            }
        },
        404: {
            'description': 'File directory not found',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
def init_data(): 
    try: 
        clear_existing_data() 
        data_folder = os.path.join(os.path.dirname(__file__), '..', '..', 'postdata') 
        companies_file = os.path.join(data_folder, 'companies.csv')
        if not os.path.exists(data_folder):
            return jsonify({"error": f"Data folder not found: {data_folder}"}), 404
        results = {}
        
        if os.path.exists(companies_file):
            results['companies'] = load_companies(companies_file)
        
        branches_file = os.path.join(data_folder, 'branches.csv')
        if os.path.exists(branches_file):
            results['branches'] = load_branches(branches_file)
        
        meters_file = os.path.join(data_folder, 'water_meters.csv')
        if os.path.exists(meters_file):
            results['water_meters'] = load_water_meters(meters_file)
        
        models_file = os.path.join(data_folder, 'ai_models.csv')
        if os.path.exists(models_file):
            results['ai_models'] = load_ai_models(models_file)
        
        measurements_file = os.path.join(data_folder, 'measurements.csv')
        if os.path.exists(measurements_file):
            results['measurements'] = load_measurements(measurements_file)
            results['threshold_calculation'] = calculate_thresholds_for_all_meters()
            results['auto_predictions'] = auto_generate_predictions()
        
        predictions_file = os.path.join(data_folder, 'predictions.csv')
        if os.path.exists(predictions_file):
            results['predictions'] = load_predictions(predictions_file)
        
        return jsonify({
            "message": "Test data initialized successfully",
            "results": results
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
            
def clear_existing_data():
    collections = ['companies', 'branches', 'water_meters', 'ai_models', 
                  'meter_measurement_data', 'predictions']
    
    for collection in collections: 
        mongo.db[collection].delete_many({})

def load_companies(file_path): 
    companies = []

    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            company = {
                'company_id': int(row['company_id']),
                'name': row['name'],
                'address': row['address']
            }
            companies.append(company)
    
    if companies:
        mongo.db.companies.insert_many(companies)
    return len(companies)

def load_branches(file_path): 
    branches = []

    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            branch = {
                'branch_id': int(row['branch_id']),
                'company_id': int(row['company_id']),
                'name': row['name'],
                'address': row['address']
            }
            branches.append(branch)
    
    if branches:
        mongo.db.branches.insert_many(branches)
    return len(branches)

def load_water_meters(file_path):
    meters = []
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            meter = {
                'meter_id': int(row['meter_id']),
                'branch_id': int(row['branch_id']),
                'meter_name': row['meter_name'],
                'installation_time': row['installation_time'],
                'threshold': 0.015  
            }
            meters.append(meter)
    if meters: 
        mongo.db.water_meters.insert_many(meters)
    return len(meters)

def load_ai_models(file_path):
    models = []
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            model = {
                'model_id': int(row['model_id']),
                'name': row['name'],
                'trained_date': row['trained_date']
            }
            models.append(model)
    
    if models:
        mongo.db.ai_models.insert_many(models)
    return len(models)

def load_measurements(file_path):
    measurements = []
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            measurement = {
                'id': int(row['id']),
                'meter_id': int(row['meter_id']),
                'instant_flow': float(row['instant_flow']),
                'measurement_time': row['measurement_time'],
                'instant_pressure': float(row['instant_pressure']) if row['instant_pressure'] else None
            }
            measurements.append(measurement)
    
    if measurements:
        mongo.db.meter_measurement_data.insert_many(measurements)
    return len(measurements)

def load_predictions(file_path):
    predictions = []
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            prediction = {
                'p_id': int(row['p_id']),
                'meter_id': int(row['meter_id']),
                'model_id': int(row['model_id']),
                'prediction_time': row['prediction_time'],
                'prediction_threshold': float(row['prediction_threshold']),
                'predicted_label': row['predicted_label'],
                'confidence': float(row['confidence']),
                'recorded_instant_flow': float(row['recorded_instant_flow'])
            }
            predictions.append(prediction)
    
    if predictions:
        mongo.db.predictions.insert_many(predictions)
    return len(predictions)

def auto_generate_predictions():
    try:
        from app.ml.predict import predictor
        
        try:
            predictor.load_model()
        except Exception as e:
            print(f"Warning: Could not load ML model for predictions: {e}")
            return 0
            
        meters = list(mongo.db.water_meters.find({}))
        
        if not meters:
            print("No water meters found")
            return 0
            
        total_predictions = 0
        
        for meter in meters:
            meter_id = meter['meter_id']
            
            last_measurements = list(
                mongo.db.meter_measurement_data
                .find({"meter_id": meter_id})
                .sort("measurement_time", -1)
                .limit(10)
            )
            
            if len(last_measurements) < 10:
                print(f"Meter {meter_id}: Only {len(last_measurements)} measurements found, skipping")
                continue
                
            last_measurements.reverse()
            
            last_prediction = mongo.db.predictions.find_one(sort=[("p_id", -1)])
            next_p_id = (last_prediction.get("p_id", 0) + 1) if last_prediction else 1
            
            predictions_to_insert = []
            
            for measurement in last_measurements:
                try:
                    meter_doc = mongo.db.water_meters.find_one({"meter_id": meter_id})
                    meter_threshold = meter_doc.get('threshold', 0.015) if meter_doc else 0.015
                    
                    is_anomaly, confidence, reconstruction_error, _ = predictor.predict_one(
                        meter_id, measurement['instant_flow']
                    )
                    
                    prediction = {
                        "p_id": next_p_id,
                        "meter_id": meter_id,
                        "model_id": 1,  
                        "prediction_time": measurement['measurement_time'],
                        "prediction_threshold": meter_threshold, 
                        "predicted_label": "Rò rỉ" if is_anomaly else "Bình thường",
                        "confidence": confidence,
                        "recorded_instant_flow": measurement['instant_flow']
                    }
                    
                    predictions_to_insert.append(prediction)
                    next_p_id += 1
                    
                except Exception as e:
                    print(f"Error predicting for meter {meter_id}, measurement {measurement['id']}: {e}")
                    continue
            
            if predictions_to_insert:
                mongo.db.predictions.insert_many(predictions_to_insert)
                total_predictions += len(predictions_to_insert)
                print(f"Generated {len(predictions_to_insert)} predictions for meter {meter_id}")
        
        print(f"Auto-generated {total_predictions} predictions total")
        return total_predictions
        
    except Exception as e:
        print(f"Error in auto_generate_predictions: {e}")
        return 0

def calculate_thresholds_for_all_meters():
    try:
        from app.ml.predict import predictor
        
        try:
            predictor.load_model()
        except Exception as e:
            print(f"Warning: Could not load ML model for threshold calculation: {e}")
            return 0
            
        meters = list(mongo.db.water_meters.find({}))
        
        if not meters:
            print("No water meters found for threshold calculation")
            return 0
            
        updated_count = 0
        
        for meter in meters:
            meter_id = meter['meter_id']
            
            try:
                threshold = predictor.calculate_threshold(meter_id, days_back=7, percentile=90)
                
                mongo.db.water_meters.update_one(
                    {"meter_id": meter_id},
                    {"$set": {"threshold": threshold}}
                )
                
                updated_count += 1
                print(f"Updated threshold for meter {meter_id}: {threshold:.6f}")
                
            except Exception as e:
                print(f"Error calculating threshold for meter {meter_id}: {e}")
                continue
        
        print(f"Successfully calculated thresholds for {updated_count} meters")
        return updated_count
        
    except Exception as e:
        print(f"Error in calculate_thresholds_for_all_meters: {e}")
        return 0