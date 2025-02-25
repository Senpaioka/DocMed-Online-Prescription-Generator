from app.app import db
from datetime import datetime
from flask_login import UserMixin
from app.dashboard.models import ProfileSetupModel
from app.pdf.models import PrescriptionModel



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
    # admin
    is_admin = db.Column(db.Boolean(), default=False, nullable=False)
    is_active = db.Column(db.Boolean(), default=True, nullable=False)

    def __repr__(self):
        return self.username
    
    def get_id(self):
        return self.uid
    
