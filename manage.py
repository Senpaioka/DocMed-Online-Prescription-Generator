from serverless_wsgi import handle_request
from app.app import create_app

# Create the Flask application
flask_app = create_app()

# Vercel needs this handler function
def vercel_handler(event, context):
    return handle_request(flask_app, event, context)

# Run Flask app locally for testing
if __name__ == '__main__':
    flask_app.run()
