from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
import os
# admin
from flask_admin import Admin, AdminIndexView
from flask_admin.menu import MenuLink
from decouple import config

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/static')
    app.config["SQLALCHEMY_DATABASE_URI"] = config('DATABASE_URL')
    app.config['DEBUG'] = config('DEBUG', default=False, cast=bool)
    db.init_app(app)

    

    # csrf secret key settings
    WTF_CSRF_SECRET_KEY = config('WTF_CSRF_SECRET_KEY')
    app.config['SECRET_KEY'] = WTF_CSRF_SECRET_KEY

    # all models & forms   
    from app.account.models import RegistrationModel
    from app.account.forms import RegistrationAdminForm
    from app.dashboard.models import ProfileSetupModel
    from app.dashboard.forms import ProfileSetUpAdminForm
    from app.pdf.models import PrescriptionModel
    from app.pdf.forms import PrescriptionAdminForm

    # flask login
    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(uid):
        return RegistrationModel.query.get(uid)
    
    
    # signature upload settings
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static','uploads')
    # Ensure the upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Optional: limit file size to 16MB
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # admin panel settings
    # Custom Admin View with Authentication Restriction
    class AdminPanel(AdminIndexView):
        # Restrict access
        def is_accessible(self):
            return current_user.is_authenticated and current_user.is_admin  

        # Redirect to login if not authorized
        def inaccessible_callback(self, name, **kwargs):
            return redirect(url_for("accounts.login_page"))
        
          
    admin = Admin(app, index_view=AdminPanel(), name='DocMed-Admin-Panel')
    # adding to admin-panel
    admin.add_view(RegistrationAdminForm(RegistrationModel, db.session))
    admin.add_view(ProfileSetUpAdminForm(ProfileSetupModel, db.session))
    admin.add_view(PrescriptionAdminForm(PrescriptionModel, db.session))
    admin.add_link(MenuLink(name='Home Page', url='/', category='Links'))
    admin.add_link(MenuLink(name='Dashboard', url=lambda: url_for('dashboard.dashboard_main_page', uid=current_user.uid) , category='Links'))


    # importing blueprints
    from app.home.routes import home
    from app.account.routes import accounts
    from app.dashboard.routes import dashboard
    from app.pdf.routes import pdf_generator
    from app.search.routes import user_search

    # register blueprints
    app.register_blueprint(home, url_prefix='/')
    app.register_blueprint(accounts, url_prefix='/account')
    app.register_blueprint(dashboard, url_prefix='/dashboard')
    app.register_blueprint(pdf_generator, url_prefix='/pdf')
    app.register_blueprint(user_search, url_prefix='/search')

    migrate.init_app(app, db)
    return app

