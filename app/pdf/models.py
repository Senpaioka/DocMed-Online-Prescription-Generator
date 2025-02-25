from app.app import db
from datetime import datetime


class PrescriptionModel(db.Model):

    __tablename__ = 'prescription'

    id = db.Column(db.Integer, primary_key=True)
    patient_id =  db.Column(db.String(15), unique=True, nullable=False)
    doc_id = db.Column(db.Integer, db.ForeignKey('registration.uid'), nullable=False)
    patient_name = db.Column(db.String(50), nullable=False)
    patient_age = db.Column(db.Integer(), nullable=False)
    patient_sex = db.Column(db.String(10), nullable=False)

    cc = db.Column(db.String(255), nullable=True)
    bp = db.Column(db.String(20), nullable=True)
    pulse = db.Column(db.String(20), nullable=True)
    temp = db.Column(db.String(20), nullable=True)
    spo = db.Column(db.String(20), nullable=True)
    inv = db.Column(db.String(255), nullable = True)

    rx = db.Column(db.Text(), nullable=False) 
    advice = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime(), default=datetime.now)

    def __repr__(self):
        return f'{self.patient_id} : {self.patient_name}'
    
    def get_id(self):
        return self.id
    