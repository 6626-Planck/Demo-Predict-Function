# Hướng dẫn chạy hệ thống

## 1. Chạy Backend (API server)

### Yêu cầu
- Python 3.8+
- MongoDB (đảm bảo đã chạy MongoDB local)
- Cài đặt các thư viện cần thiết:

```sh
cd ../be
pip install -r requirements.txt
```

### Chạy server
```sh
python run.py
```
- API sẽ chạy mặc định tại `http://localhost:5000`

## 2. Chạy Frontend (Angular)

### Yêu cầu
- Node.js >= 16
- npm

### Cài đặt dependencies
```sh
cd fe
npm install
```

### Chạy ứng dụng Angular
```sh
npm serve --open
```
- Ứng dụng sẽ chạy tại `http://localhost:4200` và kết nối tới backend ở `http://localhost:5000`

---

**Lưu ý:**  
- Đảm bảo backend đã chạy trước khi mở frontend để frontend có thể lấy dữ liệu từ API.
---
