import os 
from dotenv import load_dotenv

load_dotenv()
class MLConfig: 
    LSTM_AE_MODEL_PATH = os.getenv('LSTM_AE_MODEL_PATH', 'app/ml/models/lstm_autoencoder/lstm_ae.pth')

    LSTM_AE_CONFIG = {
        'input_size': int(os.getenv("LSTMAE_INPUT_SIZE", "1")),  
        'hidden_size': int(os.getenv("LSTMAE_HIDDEN_SIZE", "32")),
        'num_layers': int(os.getenv("LSTMAE_NUM_LAYERS", "1")),
        'dropout_ratio': float(os.getenv("LSTMAE_DROPOUT_RATIO", "0.1")),
        'seq_len': int(os.getenv("LSTMAE_SEQ_LEN", "168")),  
        'use_act': os.getenv("LSTMAE_USE_ACT", "true").lower() == "true",
    }