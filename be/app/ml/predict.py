import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, timedelta
import os
from app.database import mongo
from .config import MLConfig
try:
    from app.ml.models.lstm_autoencoder.lstm_autoencoder import LSTMAE
except ImportError as e:
    print(f"Warning: Could not import LSTMAE model: {e}")
    LSTMAE = None

class LSTMAEPredictor:
    def __init__(self, model_path=None, config=None):
        self.model_path = model_path or os.path.join(os.path.dirname(__file__), 'models/lstm_autoencoder/lstm_ae.pth')
        self.config = config or {
            'input_size': 1,
            'hidden_size': 32,
            'num_layers': 1,
            'dropout_ratio': 0.1,
            'seq_len': 168,  # 7 days * 24 hours
            'use_act': True
        }
        self.model = None
        self.scaler = MinMaxScaler()
        self.threshold = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def load_model(self):
        if LSTMAE is None:
            print("Không tìm thấy lớp LSTM-AutoEncoder!")
            return
            
        self.model = LSTMAE(**self.config)
        if os.path.exists(self.model_path):
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            print(f"Đã tải mô hình từ {self.model_path}")
        else:
            print(f"Không tìm thấy tệp mô hình tại {self.model_path}, sử dụng mô hình chưa được huấn luyện")
        self.model.to(self.device)
        self.model.eval()
        
    def prepare_data(self, data, fit_scaler=False):
        data = np.array(data).reshape(-1, 1)
        if fit_scaler:
            data_scaled = self.scaler.fit_transform(data)
        else:
            data_scaled = self.scaler.transform(data)
        return data_scaled.flatten()
        
    def calculate_threshold(self, meter_id, days_back=7, percentile=90):
        try:
            if self.model is None:
                self.load_model()
                
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            historical_data = list(mongo.db.meter_measurement_data.find({
                "meter_id": meter_id,
                "measurement_time": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }).sort("measurement_time", 1))
            
            if len(historical_data) < self.config['seq_len'] * 2:
                print(f"Không đủ dữ liệu trong {days_back} ngày, lấy tất cả dữ liệu có sẵn")
                historical_data = list(mongo.db.meter_measurement_data.find({
                    "meter_id": meter_id
                }).sort("measurement_time", 1))
            
            if len(historical_data) < self.config['seq_len']:
                print(f"Không đủ dữ liệu lịch sử cho đồng hồ {meter_id}")
                return 0.015  
                
            flow_rates = [float(row['instant_flow']) for row in historical_data]
            flow_data_scaled = self.prepare_data(flow_rates, fit_scaler=True)
            
            sequences = []
            for i in range(len(flow_data_scaled) - self.config['seq_len'] + 1):
                seq = flow_data_scaled[i:i + self.config['seq_len']]
                sequences.append(seq)
                
            if len(sequences) == 0:
                return 0.015
                
            sequences = np.array(sequences)[:, :, np.newaxis]
            
            reconstruction_errors = []
            self.model.eval()
            with torch.no_grad():
                for seq in sequences:
                    seq_tensor = torch.FloatTensor(seq).unsqueeze(0).to(self.device)
                    reconstructed = self.model(seq_tensor)
                    point_errors = torch.mean((seq_tensor - reconstructed) ** 2, dim=2)
                    last_error = point_errors[0, -1].item()
                    reconstruction_errors.append(last_error)
            
            self.threshold = np.percentile(reconstruction_errors, percentile)
            print(f"Tính ngưỡng cho đồng hồ {meter_id}: {self.threshold:.6f} (percentile {percentile})")
            print(f"Meter {meter_id} - Số sequences: {len(sequences)}, Số errors: {len(reconstruction_errors)}")
            print(f"Meter {meter_id} - Min error: {min(reconstruction_errors):.6f}, Max error: {max(reconstruction_errors):.6f}")
            print(f"Meter {meter_id} - Mean error: {np.mean(reconstruction_errors):.6f}, Std error: {np.std(reconstruction_errors):.6f}")
            
            return self.threshold
            
        except Exception as e:
            print(f"Lỗi khi tính ngưỡng: {e}")
            import traceback
            traceback.print_exc()
            return 0.015
    
    def predict_one(self, meter_id, current_flow_rate):
    
        try:
            if self.model is None:
                self.load_model()
                
            meter_doc = mongo.db.water_meters.find_one({"meter_id": meter_id})
            if meter_doc and 'threshold' in meter_doc:
                db_threshold = float(meter_doc['threshold'])
            else:
                db_threshold = None
                
            recent_data = list(mongo.db.meter_measurement_data.find({
                "meter_id": meter_id
            }).sort("measurement_time", -1).limit(self.config['seq_len'] - 1))
            
            if len(recent_data) < self.config['seq_len'] - 1:
                print(f"Không đủ dữ liệu gần đây cho đồng hồ {meter_id} (có {len(recent_data)}, cần {self.config['seq_len']-1})")
                final_threshold = db_threshold if db_threshold is not None else self.calculate_threshold(meter_id)
                return False, 0.95, 0.0, final_threshold
            
            flow_rates = [float(row['instant_flow']) for row in reversed(recent_data)] + [float(current_flow_rate)]
            
            historical_data = list(mongo.db.meter_measurement_data.find({
                "meter_id": meter_id
            }).sort("measurement_time", -1).limit(500))
            
            if len(historical_data) >= 50:
                historical_flows = [float(row['instant_flow']) for row in historical_data]
                self.prepare_data(historical_flows, fit_scaler=True)
                flow_data_scaled = self.prepare_data(flow_rates, fit_scaler=False)
            else:
                flow_data_scaled = self.prepare_data(flow_rates, fit_scaler=True)
            
            current_seq = flow_data_scaled.reshape(1, self.config['seq_len'], 1)
            current_seq_tensor = torch.FloatTensor(current_seq).to(self.device)
            
            self.model.eval()
            with torch.no_grad():
                reconstructed = self.model(current_seq_tensor)
                point_errors = torch.mean((current_seq_tensor - reconstructed) ** 2, dim=2)
                reconstruction_error = point_errors[0, -1].item() 
                
                original_last_point = current_seq_tensor[0, -1, 0].item()  
                reconstructed_last_point = reconstructed[0, -1, 0].item()  
                
                   
                original_unscaled = self.scaler.inverse_transform([[original_last_point]])[0][0]
                reconstructed_unscaled = self.scaler.inverse_transform([[reconstructed_last_point]])[0][0]
                print(f"Meter {meter_id} - Flow gốc: {original_unscaled:.3f}, Flow tái tạo: {reconstructed_unscaled:.3f}")                
                print(f"Meter {meter_id} - Reconstruction error: {reconstruction_error:.6f}") 
            
            if db_threshold is not None:
                final_threshold = db_threshold
            else:
                print("Tính ngưỡng từ dữ liệu lịch sử...")
                final_threshold = self.calculate_threshold(meter_id, days_back=7, percentile=90)
                mongo.db.water_meters.update_one(
                    {"meter_id": meter_id},
                    {"$set": {"threshold": final_threshold}}
                )
            
            is_anomaly = reconstruction_error > final_threshold
            if reconstructed_unscaled > original_unscaled: 
                is_anomaly = False

            flow_diff_ratio = abs(reconstructed_unscaled - original_unscaled) / max(abs(original_unscaled), 1e-3)
            error_factor = min(reconstruction_error / max(final_threshold, 1e-8), 3.0)  
            
            if is_anomaly:
                combined_factor = 0.7 * error_factor + 0.3 * flow_diff_ratio
                confidence = min(0.95, 0.60 + 0.35 * min(combined_factor, 1.0))
                print(f"Meter {meter_id} - ANOMALY: error_factor={error_factor:.3f}, flow_diff_ratio={flow_diff_ratio:.3f}, confidence={confidence:.3f}")
            else:
                normal_factor = 1.0 - min(error_factor / 2.0, 1.0)  
                confidence = max(0.75, 0.75 + 0.20 * normal_factor)
                print(f"Meter {meter_id} - NORMAL: error_factor={error_factor:.3f}, normal_factor={normal_factor:.3f}, confidence={confidence:.3f}")
                
            print(f"Meter {meter_id} - Flow diff: {abs(reconstructed_unscaled - original_unscaled):.3f} ({flow_diff_ratio*100:.1f}%)")

            print(f"Prediction for meter {meter_id}: reconstructed_value={reconstructed[0, -1].item()} anomaly={is_anomaly}, confidence={confidence:.3f}, error={reconstruction_error:.6f}, threshold={final_threshold:.6f}")

            return is_anomaly, confidence, reconstruction_error, final_threshold
            
        except Exception as e:
            print(f"Lỗi trong prediction: {e}")
            import traceback
            traceback.print_exc()
            fallback_threshold = db_threshold if db_threshold is not None else 0.015
            return False, 0.95, 0.0, fallback_threshold

predictor = LSTMAEPredictor(config=MLConfig.LSTM_AE_CONFIG, model_path=MLConfig.LSTM_AE_MODEL_PATH)