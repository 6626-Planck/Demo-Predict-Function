from flask import Blueprint, request, jsonify
from app.database import mongo
from app.models import WaterMeter
from datetime import datetime
from flasgger import swag_from
from app.ml.predict import predictor
import threading

water_meter_bp = Blueprint('water_meter', __name__)

def get_next_meter_id(): 
    last_meter = mongo.db.water_meters.find_one(sort=[("meter_id", -1)])
    return last_meter["meter_id"] + 1 if last_meter else 1

def get_next_prediction_id():
    last_prediction = mongo.db.predictions.find_one(sort=[("p_id", -1)])
    return last_prediction["p_id"] + 1 if last_prediction else 1

def process_prediction_async(meter_id, flow_rate, measurement_time):
    try:
        is_anomaly, confidence, reconstruction_error, threshold = predictor.predict_one(
            meter_id, flow_rate
        )
        
        predicted_label = "Rò rỉ" if is_anomaly else "Bình thường"
        
        new_prediction = {
            'p_id': get_next_prediction_id(),
            'meter_id': meter_id,
            'model_id': 1,  
            'prediction_time': measurement_time,
            'prediction_threshold': threshold,
            'predicted_label': predicted_label,
            'confidence': confidence,
            'recorded_instant_flow': flow_rate
        }
        
        mongo.db.predictions.insert_one(new_prediction)
        
        print(f"Prediction đã lưu: Meter {meter_id}, Label: {predicted_label}, Confidence: {confidence:.3f}")
        
    except Exception as e:
        print(f"Lỗi trong quá trình prediction: {e}") 


@water_meter_bp.route('/water_meters', methods=['POST'])
@swag_from({
    'tags': ['Đồng hồ nước'],
    'summary': 'Tạo mới một đồng hồ nước', 
    'description': 'API để tạo mới một đồng hồ nước trong hệ thống với thông tin chi nhánh và thời gian lắp đặt',
    'parameters': [
        {
            'name': 'body', 
            'in': 'body',
            'required': True,
            'description': 'Thông tin đồng hồ nước cần tạo',
            'schema': {
                'type': 'object',
                'properties': {
                    'branch_id': {
                        'type': 'integer',
                        'description': 'ID của chi nhánh'
                    },
                    'meter_name': {
                        'type': 'string',
                        'description': 'Tên đồng hồ nước'
                    },
                    'installation_time': {
                        'type': 'string', 
                        'format': 'date-time',
                        'description': 'Thời gian lắp đặt (định dạng ISO 8601)'
                    }
                },
                'required': ['branch_id', 'meter_name', 'installation_time']
            }
        }
    ],
    'responses': { 
        201: {
            'description': 'Tạo đồng hồ nước thành công',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'meter_id': {'type': 'integer'}
                }
            }
        },
        400: {'description': 'Dữ liệu đầu vào không hợp lệ'},
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def create_water_meter(): 
    try: 
        data = request.get_json()

        if not data: 
            return jsonify({"error": "Invalid input data"}), 400
        
        if 'branch_id' not in data or 'meter_name' not in data or 'installation_time' not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        meter_id = get_next_meter_id()
        new_meter = {
            'meter_id': meter_id,
            'branch_id': data['branch_id'],
            'meter_name': data['meter_name'],
            'installation_time': data.get('installation_time', datetime.utcnow().isoformat()),
            'threshold': predictor.calculate_threshold(meter_id) 
        }

        result = mongo.db.water_meters.insert_one(new_meter)

        if result.inserted_id:
            new_meter['_id'] = str(result.inserted_id)
            return jsonify({
                'message': 'Water meter created successfully',
                'data': WaterMeter.to_dict(new_meter)
            }), 201
        else: 
            return jsonify({"error": "Failed to create water meter"}), 500
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    

@water_meter_bp.route('/water_meters', methods=['GET'])
@swag_from({
    'tags': ['Đồng hồ nước'],
    'summary': 'Lấy thông tin tất cả đồng hồ nước', 
    'parameters': [
        {
            'name': 'branch_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Filter by branch ID'
        },
        {
            'name': 'page',
            'in': 'query',
            'type': 'integer',
            'default': 1,
            'description': 'Page number'
        },
        {
            'name': 'limit',
            'in': 'query',
            'type': 'integer',
            'default': 10,
            'description': 'Number of items per page'
        }
    ],
    'responses': { 
        200: {'description': 'Successfully'},
        500: {'description': 'Internal server error'}
    }
})
def get_all_water_meters(): 
    try: 
        branch_id = request.args.get('branch_id', type=int)
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)

        query_filter = {}
        if branch_id: 
            query_filter['branch_id'] = branch_id
        skip = (page - 1) * limit

        meters = list(mongo.db.water_meters.find(query_filter).skip(skip).limit(limit))
        total_count = mongo.db.water_meters.count_documents(query_filter)

        meters_data = [WaterMeter.to_dict(meter) for meter in meters]
        return jsonify({
            'data': meters_data,
            'total_count': total_count,
            'page': page,
            'limit': limit
        }), 200
    except Exception as e:  
        return jsonify({"error": str(e)}), 500

@water_meter_bp.route('/water_meters/<int:meter_id>/predictions', methods=['GET'])
@swag_from({
    'tags': ['Đồng hồ nước'],
    'summary': 'Lấy dữ liệu dự đoán cho một đồng hồ nước cụ thể',
    'parameters': [
        {
            'name': 'meter_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Water meter ID'
        },
        {
            'name': 'page',
            'in': 'query',
            'type': 'integer',
            'default': 1,
            'description': 'Page number'
        },
        {
            'name': 'limit',
            'in': 'query',
            'type': 'integer',
            'default': 20,
            'description': 'Number of predictions per page'
        },
        {
            'name': 'start_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'description': 'Filter predictions from this date (YYYY-MM-DD)'
        },
        {
            'name': 'end_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'description': 'Filter predictions to this date (YYYY-MM-DD)'
        }
    ],
    'responses': {
        200: {
            'description': 'Predictions data retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'prediction_time': {'type': 'string', 'format': 'date-time'},
                                'recorded_instant_flow': {'type': 'number'},
                                'predicted_label': {'type': 'string'},
                                'confidence': {'type': 'number'},
                            }
                        }
                    },
                    'total_count': {'type': 'integer'},
                    'page': {'type': 'integer'},
                    'limit': {'type': 'integer'},
                    'meter_info': {
                        'type': 'object',
                        'properties': {
                            'meter_id': {'type': 'integer'},
                            'meter_name': {'type': 'string'}
                        }
                    }
                }
            }
        },
        404: {'description': 'Water meter not found'},
        500: {'description': 'Internal server error'}
    }
})
def get_water_meter_details_predictions(meter_id): 
    try: 
        meter = mongo.db.water_meters.find_one({"meter_id": meter_id})
        if not meter: 
            return jsonify({"error": "Water meter not found"}), 404
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query_filter = {"meter_id": meter_id}

        if start_date or end_date:
            time_filter = {}
            if start_date:
                time_filter["$gte"] = start_date + "T00:00:00"
            if end_date:
                time_filter["$lte"] = end_date + "T23:59:59"
            query_filter["prediction_time"] = time_filter

        skip = (page - 1) * limit
        predictions = list(mongo.db.predictions.find(query_filter)
                           .sort("prediction_time", -1)
                           .skip(skip)
                           .limit(limit))
        total_count = mongo.db.predictions.count_documents(query_filter)
        predictions_data = []
        for pred in predictions:
            prediction_time = pred.get('prediction_time', '')
            if isinstance(prediction_time, str):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(prediction_time.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%H:%M %d/%m/%Y')
                except:
                    formatted_time = prediction_time
            else:
                formatted_time = str(prediction_time)

            confidence = pred.get('confidence', 0) * 100

            predicted_label = pred.get('predicted_label', '')
            if predicted_label.lower() in ['bình thường', 'binh thuong', 'normal']:
                display_label = 'Bình thường'
            elif predicted_label.lower() in ['rò rỉ', 'ro ri', 'leak', 'bất thường', 'bat thuong']:
                display_label = 'Bất thường'
            else:
                display_label = predicted_label

            predictions_data.append({
                'prediction_time': formatted_time,
                'recorded_instant_flow': pred.get('recorded_instant_flow', 0),
                'predicted_label': display_label,
                'confidence': confidence,
            })

        return jsonify({
            'data': predictions_data,
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'meter_info': {
                'meter_id': meter_id,
                'meter_name': meter.get('meter_name', f'Water Meter {meter_id}')
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@water_meter_bp.route('/water_meters/<int:meter_id>/status', methods=['GET'])
@swag_from({
    'tags': ['Đồng hồ nước'],
    'summary': 'Lấy trạng thái đồng hồ nước',
    'description': 'Lấy trạng thái hiện tại của đồng hồ nước dựa trên kết quả dự đoán mới nhất',
    'parameters': [
        {
            'name': 'meter_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID của đồng hồ nước'
        }
    ],
    'responses': {
        200: {
            'description': 'Lấy trạng thái đồng hồ nước thành công',
            'schema': {
                'type': 'object',
                'properties': {
                    'meter_id': {'type': 'integer'},
                    'meter_name': {'type': 'string'},
                    'status': {'type': 'string', 'enum': ['BÌNH THƯỜNG', 'RÒ RỈ']}
                }
            }
        },
        404: {'description': 'Không tìm thấy đồng hồ nước'},
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def get_water_meter_status(meter_id):
    try:
        meter = mongo.db.water_meters.find_one({"meter_id": meter_id})
        if not meter:
            return jsonify({"error": "Không tìm thấy đồng hồ nước"}), 404

        latest_predictions = list(mongo.db.predictions.find({"meter_id": meter_id})
                                 .sort("prediction_time", -1)
                                 .limit(1))
        
        if not latest_predictions:
            return jsonify({
                "meter_id": meter_id,
                "meter_name": meter.get("meter_name"),
                "status": "BÌNH THƯỜNG",
            }), 200

        all_normal = all(pred.get("predicted_label", "").lower() in ["bình thường", "binh thuong", "normal"] 
                        for pred in latest_predictions)
        
        status = "BÌNH THƯỜNG" if all_normal else "RÒ RỈ"

        return jsonify({
            "meter_id": meter_id,
            "meter_name": meter.get("meter_name"),
            "status": status,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@water_meter_bp.route('/water_meters/status', methods=['GET'])
@swag_from({
    'tags': ['Đồng hồ nước'],
    'summary': 'Lấy trạng thái tất cả đồng hồ nước',
    'description': 'Lấy trạng thái hiện tại của tất cả đồng hồ nước trong hệ thống',
    'parameters': [
        {
            'name': 'branch_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Lọc theo ID chi nhánh (tùy chọn)'
        }
    ],
    'responses': {
        200: {
            'description': 'Lấy trạng thái tất cả đồng hồ nước thành công',
            'schema': {
                'type': 'object',
                'properties': {
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'meter_id': {'type': 'integer'},
                                'meter_name': {'type': 'string'},
                                'branch_id': {'type': 'integer'},
                                'status': {'type': 'string', 'enum': ['BÌNH THƯỜNG', 'RÒ RỈ']}
                            }
                        }
                    }
                }
            }
        },
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def get_all_water_meters_status():
    try:
        branch_id = request.args.get('branch_id', type=int)
        
        query_filter = {}
        if branch_id:
            query_filter['branch_id'] = branch_id
            
        meters = list(mongo.db.water_meters.find(query_filter))
        
        result = []
        for meter in meters:
            meter_id = meter['meter_id']
            
            latest_predictions = list(mongo.db.predictions.find({"meter_id": meter_id})
                                     .sort("prediction_time", -1)
                                     .limit(1))
            
            if not latest_predictions:
                result.append({
                    "meter_id": meter_id,
                    "meter_name": meter.get("meter_name"),
                    "branch_id": meter.get("branch_id"),
                    "status": "BÌNH THƯỜNG",
                })
                continue
            
            all_normal = all(pred.get("predicted_label", "").lower() in ["bình thường", "binh thuong", "normal"] 
                            for pred in latest_predictions)
            
            status = "BÌNH THƯỜNG" if all_normal else "RÒ RỈ"
            
            result.append({
                "meter_id": meter_id,
                "meter_name": meter.get("meter_name"),
                "branch_id": meter.get("branch_id"),
                "status": status,
            })
        
        return jsonify({"data": result}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@water_meter_bp.route('/water_meters/<int:meter_id>/measurements', methods=['POST'])
@swag_from({
    'tags': ['Đồng hồ nước'],
    'summary': 'Ghi dữ liệu đo mới với phát hiện bất thường tự động',
    'description': 'Ghi nhận dữ liệu đo lường mới và tự động chạy thuật toán ML để phát hiện bất thường',
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
            'required': True,
            'description': 'Dữ liệu đo lường cần ghi',
            'schema': {
                'type': 'object',
                'properties': {
                    'instant_flow': {
                        'type': 'number',
                        'description': 'Lưu lượng tức thời (L/h)'
                    },
                    'measurement_time': {
                        'type': 'string',
                        'format': 'date-time',
                        'description': 'Thời gian đo (định dạng ISO 8601)'
                    },
                    'instant_pressure': {
                        'type': 'number',
                        'description': 'Áp suất tức thời (bar)'
                    }
                },
                'required': ['instant_flow', 'measurement_time']
            }
        }
    ],
    'responses': {
        201: {
            'description': 'Ghi dữ liệu đo thành công và bắt đầu dự đoán',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'measurement_id': {'type': 'integer'},
                    'prediction_processing': {'type': 'string'}
                }
            }
        },
        404: {'description': 'Không tìm thấy đồng hồ nước'},
        400: {'description': 'Dữ liệu đầu vào không hợp lệ'},
        500: {'description': 'Lỗi server nội bộ'}
    }
})
def create_measurement_with_prediction(meter_id):
    try:
        meter = mongo.db.water_meters.find_one({"meter_id": meter_id})
        if not meter:
            return jsonify({"error": "Không tìm thấy đồng hồ nước"}), 404
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dữ liệu đầu vào không hợp lệ"}), 400
            
        if 'instant_flow' not in data or 'measurement_time' not in data:
            return jsonify({"error": "Thiếu trường bắt buộc"}), 400
        
        last_measurement = mongo.db.meter_measurement_data.find_one(sort=[("id", -1)])
        new_id = last_measurement["id"] + 1 if last_measurement else 1
        
        new_measurement = {
            'id': new_id,
            'meter_id': meter_id,
            'instant_flow': float(data['instant_flow']),
            'measurement_time': data['measurement_time'],
            'instant_pressure': float(data.get('instant_pressure', 0))
        }
        
        result = mongo.db.meter_measurement_data.insert_one(new_measurement)
        
        if result.inserted_id:
            thread = threading.Thread(
                target=process_prediction_async,
                args=(meter_id, data['instant_flow'], data['measurement_time'])
            )
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'message': 'Ghi dữ liệu đo thành công',
                'measurement_id': new_id,
                'prediction_processing': 'đã bắt đầu'
            }), 201
        else:
            return jsonify({"error": "Không thể ghi dữ liệu đo"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

