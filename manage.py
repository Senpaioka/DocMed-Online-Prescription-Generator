from serverless_wsgi import handle_request
from app.app import create_app
from http.server import BaseHTTPRequestHandler




flask_app = create_app()


class handler(BaseHTTPRequestHandler):


    # Vercel needs this handler for deployment
    # def vercel_handler(event, context):
    #     return handle_request(flask_app, event, context)



    if __name__ == '__main__':
        flask_app.run()