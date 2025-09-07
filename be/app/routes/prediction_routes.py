from flask import Blueprint, request, jsonify
from app.database import mongo
from app.models import WaterMeter
from datetime import datetime
from flasgger import swag_from
from app.ml.predict import predictor
import threading

prediction_bp = Blueprint('prediction_routes', __name__)

@prediction_bp.route('/predictions/manual', methods=['POST'])
@swag_from({
    'tags': ['Dự đoán'],
    'summary': 'Thực hiện dự đoán thủ công',
    'description': 'Thực hiện dự đoán bất thường thủ công cho một đồng hồ nước với giá trị lưu lượng cụ thể (điền bằng tay để test )',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'Thông tin để thực hiện dự đoán',
            'schema': {
                'type': 'object',
                'properties': {
                    'meter_id': {
                        'type': 'integer',
                        'description': 'ID của đồng hồ nước'
                    },
                    'flow_rate': {
                        'type': 'number',
                        'description': 'Lưu lượng cần dự đoán (L/h)'
                    }
                },
                'required': ['meter_id', 'flow_rate']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Thực hiện dự đoán thành công',
            'schema': {
                'type': 'object',
                'properties': {
                    'meter_id': {'type': 'integer'},
                    'flow_rate': {'type': 'number'},
                    'is_anomaly': {'type': 'boolean'},
                    'predicted_label': {'type': 'string'},
                    'confidence': {'type': 'number'},
                    'reconstruction_error': {'type': 'number'},
                    'threshold': {'type': 'number'}
                }
            }
        },
        404: {'description': 'Không tìm thấy đồng hồ nước'},
        400: {'description': 'Dữ liệu đầu vào không hợp lệ'},
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def manual_prediction():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dữ liệu đầu vào không hợp lệ"}), 400
            
        if 'meter_id' not in data or 'flow_rate' not in data:
            return jsonify({"error": "Thiếu trường bắt buộc"}), 400
            
        meter_id = data['meter_id']
        flow_rate = data['flow_rate']
        
        meter = mongo.db.water_meters.find_one({"meter_id": meter_id})
        if not meter:
            return jsonify({"error": "Không tìm thấy đồng hồ nước"}), 404
        
        is_anomaly, confidence, reconstruction_error, threshold = predictor.predict_one(
            meter_id, flow_rate
        )
        
        predicted_label = "Rò rỉ" if is_anomaly else "Bình thường"
        
        response_data = {
            'meter_id': int(meter_id),
            'flow_rate': float(flow_rate),
            'is_anomaly': bool(is_anomaly),
            'predicted_label': str(predicted_label),
            'confidence': float(confidence),
            'reconstruction_error': float(reconstruction_error),
            'threshold': float(threshold),
            'message': 'Dự đoán thành công'
        }
        
        print(f"Response data: {response_data}")  
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in manual_prediction: {e}")  
        return jsonify({"error": str(e)}), 500


@prediction_bp.route('/predictions/threshold/<int:meter_id>', methods=['POST'])
@swag_from({
    'tags': ['Dự đoán'],
    'summary': 'Tính lại ngưỡng phát hiện bất thường',
    'description': 'Tính lại ngưỡng phát hiện bất thường dựa trên dữ liệu lịch sử của đồng hồ nước',
    'parameters': [
        {
            'name': 'meter_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID của đồng hồ nước'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': False,
            'description': 'Tham số tính toán ngưỡng',
            'schema': {
                'type': 'object',
                'properties': {
                    'days_back': {
                        'type': 'integer',
                        'default': 7,
                        'description': 'Số ngày dữ liệu lịch sử để tính toán (mặc định: 7)'
                    }
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Tính toán ngưỡng thành công',
            'schema': {
                'type': 'object',
                'properties': {
                    'meter_id': {'type': 'integer'},
                    'threshold': {'type': 'number'},
                    'days_back': {'type': 'integer'},
                    'message': {'type': 'string'}
                }
            }
        },
        404: {'description': 'Không tìm thấy đồng hồ nước'},
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def recalculate_threshold(meter_id):
    try:
        meter = mongo.db.water_meters.find_one({"meter_id": meter_id})
        if not meter:
            return jsonify({"error": "Không tìm thấy đồng hồ nước"}), 404
            
        data = request.get_json() or {}
        days_back = data.get('days_back', 7)
        
        threshold = predictor.calculate_threshold(meter_id, days_back)
        mongo.db.water_meters.update_one(
                    {"meter_id": meter_id},
                    {"$set": {"threshold": threshold}}
                )
        return jsonify({
            'meter_id': meter_id,
            'threshold': threshold,
            'days_back': days_back,
            'message': 'Tính toán ngưỡng thành công'
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@prediction_bp.route('/predictions', methods=['GET'])
@swag_from({
    'tags': ['Dự đoán'],
    'summary': 'Lấy danh sách tất cả predictions',
    'description': 'Lấy danh sách tất cả predictions có trong hệ thống',
    'parameters': [
        {
            'name': 'meter_id',
            'in': 'query',
            'type': 'integer',
            'required': False,
            'description': 'Lọc theo ID đồng hồ nước'
        },
        {
            'name': 'limit',
            'in': 'query',
            'type': 'integer',
            'required': False,
            'description': 'Giới hạn số lượng kết quả (mặc định: 50)'
        }
    ],
    'responses': {
        200: {
            'description': 'Lấy danh sách predictions thành công',
            'schema': {
                'type': 'object',
                'properties': {
                    'predictions': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'p_id': {'type': 'integer'},
                                'meter_id': {'type': 'integer'},
                                'model_id': {'type': 'integer'},
                                'prediction_time': {'type': 'string'},
                                'predicted_label': {'type': 'string'},
                                'confidence': {'type': 'number'},
                                'recorded_instant_flow': {'type': 'number'}
                            }
                        }
                    },
                    'total_count': {'type': 'integer'},
                    'message': {'type': 'string'}
                }
            }
        },
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def get_all_predictions():
    try:
        meter_id = request.args.get('meter_id', type=int)
        limit = request.args.get('limit', default=50, type=int)
        
        # Tạo filter query
        query_filter = {}
        if meter_id:
            query_filter['meter_id'] = meter_id
            
        # Lấy predictions với limit
        predictions = list(
            mongo.db.predictions
            .find(query_filter)
            .sort("prediction_time", -1)
            .limit(limit)
        )
        
        # Đếm tổng số
        total_count = mongo.db.predictions.count_documents(query_filter)
        
        # Convert ObjectId thành string
        for prediction in predictions:
            if '_id' in prediction:
                prediction['_id'] = str(prediction['_id'])
                
        return jsonify({
            'predictions': predictions,
            'total_count': total_count,
            'message': f'Lấy được {len(predictions)} predictions'
        }), 200
        
    except Exception as e:
        print(f"Error in get_all_predictions: {e}")
        return jsonify({"error": str(e)}), 500
