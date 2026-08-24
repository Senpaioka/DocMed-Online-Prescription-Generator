from flask import redirect, url_for
from flask_admin import AdminIndexView
from flask_admin.menu import MenuLink
from flask_login import current_user
from app.extensions import admin, db


class AdminPanel(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and (
            getattr(current_user, 'is_admin', False) or 
            getattr(current_user, 'role', '') == 'admin'
        )

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("accounts.login_page"))


def init_admin(app):
    admin.init_app(app, index_view=AdminPanel(name='Admin Dashboard'))

    from app.modules.account.models import RegistrationModel
    from app.modules.account.forms import RegistrationAdminForm
    from app.modules.dashboard.models import ProfileSetupModel
    from app.modules.dashboard.forms import ProfileSetUpAdminForm
    from app.modules.pdf.models import PrescriptionModel
    from app.modules.pdf.forms import PrescriptionAdminForm

    admin.add_view(RegistrationAdminForm(RegistrationModel, db.session, name='User Accounts'))
    admin.add_view(ProfileSetUpAdminForm(ProfileSetupModel, db.session, name='Doctor Profiles'))
    admin.add_view(PrescriptionAdminForm(PrescriptionModel, db.session, name='Prescriptions'))
    
    admin.add_link(MenuLink(name='Home Page', url='/', category='Navigation'))
    admin.add_link(MenuLink(
        name='Dashboard',
        url=lambda: url_for('dashboard.dashboard_main_page', uid=current_user.uid) if current_user.is_authenticated else '/account/login',
        category='Navigation'
    ))
