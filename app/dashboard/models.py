from app.app import db


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
    

    def __repr__(self):
        return self.full_name
    
    def get_id(self):
        return self.id
    
