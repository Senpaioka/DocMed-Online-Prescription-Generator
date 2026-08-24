from app.extensions import db
from datetime import datetime


class ProfileSetupModel(db.Model):

    __tablename__ = 'profile_info'

    id = db.Column(db.Integer, primary_key=True)
    # child relation
    user_id = db.Column(db.Integer, db.ForeignKey('registration.uid'))
 
    # personal
    full_name = db.Column(db.String(120), nullable=False)
    birth_date = db.Column(db.DateTime(), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    achievement = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(15), nullable=True)

    # educational
    college = db.Column(db.String(150), nullable=False)
    higher_degree = db.Column(db.String(225), nullable=True)
    course = db.Column(db.String(225), nullable=True)
    extra = db.Column(db.String(225), nullable=True)

    # professional
    current_position = db.Column(db.String(100), nullable=False)
    govt_reg = db.Column(db.String(100), nullable=False)
    office = db.Column(db.String(255), nullable=True)
     # This field stores the filename or relative path of the uploaded image.
    signature = db.Column(db.String(255), nullable=False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return self.full_name
    
    def get_id(self):
        return self.id


class AppointmentModel(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('registration.uid'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('registration.uid'), nullable=False)
    
    # Status: 'pending', 'confirmed', 'rejected', 'cancelled', 'completed'
    status = db.Column(db.String(20), default='pending', nullable=False)

    # Patient Details submitted with the request
    patient_name = db.Column(db.String(120), nullable=False)
    patient_email = db.Column(db.String(120), nullable=False)
    patient_phone = db.Column(db.String(25), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    
    # Schedule fields (assigned and confirmed by doctor)
    preferred_date = db.Column(db.Date, nullable=True)
    preferred_time = db.Column(db.String(50), nullable=True)

    # Actual schedule confirmed by doctor
    scheduled_date = db.Column(db.Date, nullable=True)
    scheduled_time = db.Column(db.String(50), nullable=True) # e.g. "10:30 AM", "05:00 PM"
    doctor_notes = db.Column(db.Text, nullable=True) # instructions, room/chamber info, or cancellation reason

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    patient = db.relationship('RegistrationModel', foreign_keys=[patient_id], backref=db.backref('patient_appointments', lazy='dynamic', cascade='all, delete-orphan'))
    doctor = db.relationship('RegistrationModel', foreign_keys=[doctor_id], backref=db.backref('doctor_appointments', lazy='dynamic', cascade='all, delete-orphan'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.status:
            self.status = 'pending'

    def __repr__(self):
        return f"<Appointment #{self.id} Patient={self.patient_name} Doctor_ID={self.doctor_id} Status={self.status}>"


class NotificationModel(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('registration.uid'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)

    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    event_type = db.Column(db.String(50), default='general', nullable=False)
    link_url = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    user = db.relationship('RegistrationModel', foreign_keys=[user_id], backref=db.backref('notifications', lazy='dynamic', cascade='all, delete-orphan'))
    appointment = db.relationship('AppointmentModel', foreign_keys=[appointment_id], backref=db.backref('notifications', lazy='dynamic'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'is_read' not in kwargs:
            self.is_read = False
        if 'created_at' not in kwargs:
            self.created_at = datetime.now()

    def __repr__(self):
        return f"<Notification #{self.id} User={self.user_id} Type={self.event_type} Read={self.is_read}>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'appointment_id': self.appointment_id,
            'title': self.title,
            'message': self.message,
            'event_type': self.event_type,
            'link_url': self.link_url,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'time_ago': self.get_time_ago()
        }

    def get_time_ago(self):
        if not self.created_at:
            return "Just now"
        delta = datetime.now() - self.created_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"


    
