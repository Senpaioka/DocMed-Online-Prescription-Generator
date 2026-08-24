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
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime(), nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.role:
            self.role = 'patient'
        if 'is_verified' not in kwargs:
            self.is_verified = False


    def __repr__(self):
        return f"{self.username} ({self.role})"
    
    def get_id(self):
        return self.uid

    @property
    def is_doctor(self):
        return self.role == 'doctor' or self.is_admin

    @property
    def is_patient(self):
        return self.role == 'patient'

    @property
    def is_admin_role(self):
        return self.role == 'admin' or self.is_admin

