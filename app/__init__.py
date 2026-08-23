import os
from flask import Flask
from app.config import config_by_name, DevelopmentConfig
from app.extensions import db, migrate, login_manager
from app.core.admin import init_admin


def create_app(config_name_or_class=None):
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
        static_url_path='/static'
    )

    # Load configuration
    if isinstance(config_name_or_class, str):
        config_class = config_by_name.get(config_name_or_class, DevelopmentConfig)
        app.config.from_object(config_class)
    elif config_name_or_class is not None:
        app.config.from_object(config_name_or_class)
    else:
        app.config.from_object(DevelopmentConfig)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'accounts.login_page'

    # User loader
    from app.modules.account.models import RegistrationModel

    @login_manager.user_loader
    def load_user(uid):
        return RegistrationModel.query.get(int(uid))

    # Ensure upload directory exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads')), exist_ok=True)

    # Initialize Admin
    init_admin(app)

    # Register Blueprints
    from app.modules.home.routes import home
    from app.modules.account.routes import accounts
    from app.modules.dashboard.routes import dashboard
    from app.modules.pdf.routes import pdf_generator
    from app.modules.search.routes import user_search

    app.register_blueprint(home, url_prefix='/')
    app.register_blueprint(accounts, url_prefix='/account')
    app.register_blueprint(dashboard, url_prefix='/dashboard')
    app.register_blueprint(pdf_generator, url_prefix='/pdf')
    app.register_blueprint(user_search, url_prefix='/search')

    return app
