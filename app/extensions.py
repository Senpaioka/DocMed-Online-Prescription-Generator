from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_admin import Admin
from flask_mailman import Mail

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
admin = Admin(name='DocMed Admin', base_template='admin/master.html', template_mode='bootstrap3')
mail = Mail()

