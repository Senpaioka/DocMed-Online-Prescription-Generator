from app.app import create_app

flask_app = create_app()

# Vercel needs this handler for deployment
def handler(event, context):
    return flask_app

if __name__ == '__main__':
    flask_app.run()