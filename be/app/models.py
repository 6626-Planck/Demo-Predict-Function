from app.database import mongo
from datetime import datetime

class Company: 
    @staticmethod
    def to_dict(company) -> dict: 
        return {
            "company_id": company.get("company_id"),
            "name": company.get("name"),
            "address": company.get("address")
        }
    
class Branch:
    @staticmethod
    def to_dict(branch) -> dict:
        return {
            "branch_id": branch.get("branch_id"),
            "company_id": branch.get("company_id"),
            "name": branch.get("name"),
            "address": branch.get("address")
        }
    
class WaterMeter:
    @staticmethod
    def to_dict(meter) -> dict:
        return {
            "meter_id": meter.get("meter_id"),
            "branch_id": meter.get("branch_id"),
            "meter_name": meter.get("meter_name"),
            "installation_time": meter.get("installation_time"),
            "threshold": meter.get("threshold", 0.0)
        }

class MeterMeasurementData:
    @staticmethod
    def to_dict(measurement_data) -> dict:
        return {
            "id": measurement_data.get("id"),
            "meter_id": measurement_data.get("meter_id"),
            "measurement_time": measurement_data.get("measurement_time"),
            "instant_flow": measurement_data.get("instant_flow"),
            "instant_pressure": measurement_data.get("instant_pressure")
        }
    
class AIModel:
    @staticmethod
    def to_dict(model) -> dict:
        return {
            "model_id": model.get("model_id"),
            "name": model.get("name"),
            "trained_date": model.get("trained_date")
        }
    
class Prediction:
    @staticmethod
    def to_dict(prediction) -> dict:
        return {
            "p_id": prediction.get("p_id"),
            "meter_id": prediction.get("meter_id"),
            "model_id": prediction.get("model_id"),
            "prediction_time": prediction.get("prediction_time"),
            "prediction_threshold": prediction.get("prediction_threshold"),
            "predicted_label": prediction.get("predicted_label"),
            "confidence": prediction.get("confidence"),
            "recorded_instant_flow": prediction.get("recorded_instant_flow")
        }
    
class Alert:
    @staticmethod
    def to_dict(alert) -> dict:
        return {
            "id": alert.get("id"),
            "p_id": alert.get("p_id"),
            "time": alert.get("time"),
            "level": alert.get("level")
        }