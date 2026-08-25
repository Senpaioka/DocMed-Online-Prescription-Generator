from app.extensions import db
from datetime import datetime
from flask_login import UserMixin
from app.modules.dashboard.models import ProfileSetupModel
from app.modules.pdf.models import PrescriptionModel



class RegistrationModel(UserMixin, db.Model):

    __tablename__ = 'registration'

    uid = db.Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    gender = db.Column(db.String(10), nullable = False)
    created_at = db.Column(db.DateTime(), default=datetime.now) 
    # parent relation
    # one to one relationship
    # using backref='registration', you can call this models data from profile_info model. example: profile.registration.email
    profile_info = db.relationship('ProfileSetupModel', backref='registration', uselist=False)
    # one to many
    prescription = db.relationship('PrescriptionModel', backref='prescription', uselist=True, cascade="all, delete-orphan", order_by='desc(PrescriptionModel.created_at)')
    # role: 'patient' (default), 'doctor', 'admin'
    role = db.Column(db.String(20), default='patient', nullable=False)
    # admin
    is_admin = db.Column(db.Boolean(), default=False, nullable=False)
    is_active = db.Column(db.Boolean(), default=True, nullable=False)
    is_verified = db.Column(db.Boolean(), default=False, nullable=False)
    verified_doctor = db.Column(db.Boolean(), default=False, nullable=False)
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime(), nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.role:
            self.role = 'patient'
        if 'is_verified' not in kwargs:
            self.is_verified = False
        if 'verified_doctor' not in kwargs:
            self.verified_doctor = False


    def __repr__(self):
        return f"{self.username} ({self.role})"
    
    def get_id(self):
        return self.uid

    @property
    def is_doctor(self):
        return self.role == 'doctor'

    @property
    def is_verified_doctor(self):
        return self.role == 'doctor' and bool(self.verified_doctor)

    @property
    def is_patient(self):
        return self.role == 'patient'

    @property
    def is_admin_role(self):
        return self.role == 'admin' or self.is_admin

    @property
    def patient_prescriptions(self):
        from app.modules.pdf.models import PrescriptionModel
        from app.modules.dashboard.models import AppointmentModel
        from sqlalchemy import or_

        patient_appointments = AppointmentModel.query.filter(
            or_(
                AppointmentModel.patient_id == self.uid,
                AppointmentModel.patient_email == self.email
            )
        ).all()

        appt_ids = [a.id for a in patient_appointments]
        appt_names = [a.patient_name for a in patient_appointments if a.patient_name]

        name_conditions = [PrescriptionModel.patient_name.ilike(f"%{self.username}%")]
        if self.profile_info and getattr(self.profile_info, 'full_name', None):
            name_conditions.append(PrescriptionModel.patient_name.ilike(f"%{self.profile_info.full_name}%"))

        for name in set(appt_names):
            if name and name.strip():
                name_conditions.append(PrescriptionModel.patient_name.ilike(f"%{name.strip()}%"))

        query_conditions = []
        if appt_ids:
            query_conditions.append(PrescriptionModel.appointment_id.in_(appt_ids))
        query_conditions.extend(name_conditions)

        return PrescriptionModel.query.filter(
            or_(*query_conditions)
        ).order_by(PrescriptionModel.created_at.desc()).all()

    def get_reset_password_token(self, expires_sec=1800):
        from itsdangerous import URLSafeTimedSerializer
        from flask import current_app
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.uid}, salt='password-reset-salt')

    @staticmethod
    def verify_reset_password_token(token, expires_sec=1800):
        from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
        from flask import current_app
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expires_sec)['user_id']
        except (SignatureExpired, BadSignature, Exception):
            return None
        return RegistrationModel.query.get(user_id)


