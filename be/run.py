from app import create_app
from app.routes.init_data import init_data
app = create_app()

if __name__ == "__main__":
    with app.app_context():
        init_data()
    app.run(debug=True)