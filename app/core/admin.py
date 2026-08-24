from flask import redirect, url_for
from flask_admin import AdminIndexView, expose
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

    @expose('/')
    def index(self):
        if not self.is_accessible():
            return self.inaccessible_callback(name='index')

        from app.modules.account.models import RegistrationModel
        from app.modules.dashboard.models import ProfileSetupModel
        from app.modules.pdf.models import PrescriptionModel

        total_users = RegistrationModel.query.count()
        total_doctors = RegistrationModel.query.filter_by(role='doctor').count()
        pending_doctors = RegistrationModel.query.filter_by(role='doctor', verified_doctor=False).count()
        total_patients = RegistrationModel.query.filter_by(role='patient').count()
        total_doctor_profiles = ProfileSetupModel.query.count()
        total_prescriptions = PrescriptionModel.query.count()
        recent_users = RegistrationModel.query.order_by(RegistrationModel.created_at.desc()).limit(10).all()

        return self.render(
            'admin/index.html',
            total_users=total_users,
            total_doctors=total_doctors,
            pending_doctors=pending_doctors,
            total_patients=total_patients,
            total_doctor_profiles=total_doctor_profiles,
            total_prescriptions=total_prescriptions,
            recent_users=recent_users
        )

    @expose('/verify-doctor/<int:uid>', methods=['POST', 'GET'])
    def verify_doctor(self, uid):
        if not self.is_accessible():
            return self.inaccessible_callback(name='verify_doctor')

        from flask import flash, request
        from app.modules.account.models import RegistrationModel
        from app.core.email_service import send_doctor_approval_email

        doctor = RegistrationModel.query.get_or_404(uid)
        doctor.verified_doctor = True
        db.session.commit()

        # Send congratulations email to doctor
        dashboard_url = url_for('dashboard.dashboard_main_page', uid=doctor.uid, _external=True)
        email_sent = send_doctor_approval_email(doctor, dashboard_url=dashboard_url)
        if email_sent:
            flash(f"Doctor '{doctor.username}' has been successfully verified! A congratulations email was sent to {doctor.email}.", "success")
        else:
            flash(f"Doctor '{doctor.username}' has been successfully verified, but email notification could not be delivered.", "warning")
        return redirect(request.referrer or url_for('admin.index'))

    @expose('/revoke-doctor/<int:uid>', methods=['POST', 'GET'])
    def revoke_doctor(self, uid):
        if not self.is_accessible():
            return self.inaccessible_callback(name='revoke_doctor')

        from flask import flash, request
        from app.modules.account.models import RegistrationModel

        doctor = RegistrationModel.query.get_or_404(uid)
        doctor.verified_doctor = False
        db.session.commit()
        flash(f"Doctor '{doctor.username}' verification has been revoked.", "info")
        return redirect(request.referrer or url_for('admin.index'))


def init_admin(app):
    admin.init_app(
        app,
        index_view=AdminPanel(
            name='Dashboard',
            template='admin/index.html',
            url='/admin'
        )
    )

    from app.modules.account.models import RegistrationModel
    from app.modules.account.forms import RegistrationAdminForm
    from app.modules.dashboard.models import ProfileSetupModel, AppointmentModel
    from app.modules.dashboard.forms import ProfileSetUpAdminForm, AppointmentAdminForm
    from app.modules.pdf.models import PrescriptionModel
    from app.modules.pdf.forms import PrescriptionAdminForm

    admin.add_view(RegistrationAdminForm(RegistrationModel, db.session, name='User Accounts'))
    admin.add_view(ProfileSetUpAdminForm(ProfileSetupModel, db.session, name='Doctor Profiles'))
    admin.add_view(AppointmentAdminForm(AppointmentModel, db.session, name='Appointments'))
    admin.add_view(PrescriptionAdminForm(PrescriptionModel, db.session, name='Prescriptions'))
    
    admin.add_link(MenuLink(name='Home Page', url='/', category='Navigation'))
    admin.add_link(MenuLink(name='Log Out', url='/account/logout', category='Navigation'))
