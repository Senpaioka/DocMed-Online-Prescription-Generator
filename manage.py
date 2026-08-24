from dotenv import load_dotenv
from app import create_app

load_dotenv()

flask_app = create_app()

if __name__ == '__main__':
    flask_app.run()

