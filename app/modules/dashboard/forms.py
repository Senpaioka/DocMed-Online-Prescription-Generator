from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, SubmitField, FileField, FloatField
from wtforms.validators import DataRequired, Length, Optional
from flask_wtf.file import FileAllowed, FileRequired
from flask_admin.contrib.sqla import ModelView


class ProfileSetUpForm(FlaskForm):
    full_name = StringField('full_name', validators=[DataRequired(), Length(min=5, max=120)])
    birth_date = DateField('birth_date', validators=[DataRequired()])
    sex = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    achievement = StringField('achieve', validators=[DataRequired()])
    phone = StringField('phone', validators=[Optional()])
    college = StringField('college', validators=[DataRequired()])
    higher_degree = StringField('higher_degree', validators=[Optional()])
    course = StringField('course', validators=[Optional()])
    extra = StringField('extra', validators=[Optional()])
    current_position = StringField('current_position', validators=[DataRequired()])
    govt_reg = StringField('reg_no', validators=[DataRequired()])
    office = StringField('address', validators=[Optional()])
    consultation_fee = FloatField('consultation_fee', default=1000.0, validators=[Optional()])
    signature = FileField('sign', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'svg'], 'Images only!'), FileRequired()])

    submit = SubmitField('Submit')


class UpdateProfileSetUpForm(FlaskForm):
    full_name = StringField('full_name', validators=[DataRequired(), Length(min=5, max=120)])
    birth_date = DateField('birth_date', validators=[DataRequired()])
    sex = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    achievement = StringField('achieve', validators=[DataRequired()])
    phone = StringField('phone', validators=[Optional()])
    college = StringField('college', validators=[DataRequired()])
    higher_degree = StringField('higher_degree', validators=[Optional()])
    course = StringField('course', validators=[Optional()])
    extra = StringField('extra', validators=[Optional()])
    current_position = StringField('current_position', validators=[DataRequired()])
    govt_reg = StringField('reg_no', validators=[DataRequired()])
    office = StringField('address', validators=[Optional()])
    consultation_fee = FloatField('consultation_fee', default=1000.0, validators=[Optional()])
    signature = FileField('sign', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'svg'], 'Images only!'), Optional()])

    submit = SubmitField('Update Info')


####### Admin Panel Views ########

class AppointmentAdminForm(ModelView):
    column_list = ['id', 'patient_name', 'patient_email', 'patient_phone', 'status', 'fee_amount', 'payment_status', 'scheduled_date', 'scheduled_time', 'created_at']
    column_labels = {
        'id': 'ID',
        'patient_name': 'Patient Name',
        'patient_email': 'Patient Email',
        'patient_phone': 'Phone',
        'status': 'Status',
        'fee_amount': 'Fee (BDT)',
        'payment_status': 'Payment',
        'scheduled_date': 'Confirmed Date',
        'scheduled_time': 'Confirmed Time',
        'created_at': 'Requested At'
    }
    column_searchable_list = ['patient_name', 'patient_email', 'patient_phone', 'transaction_id']
    column_filters = ['status', 'payment_status', 'scheduled_date']
    can_create = False


class PaymentTransactionAdminForm(ModelView):
    column_list = ['id', 'tran_id', 'amount', 'currency', 'status', 'card_type', 'bank_tran_id', 'created_at']
    column_labels = {
        'id': 'ID',
        'tran_id': 'Transaction ID',
        'amount': 'Amount',
        'currency': 'Currency',
        'status': 'Status',
        'card_type': 'Payment Method',
        'bank_tran_id': 'Bank Tran ID',
        'created_at': 'Initiated At'
    }
    column_searchable_list = ['tran_id', 'val_id', 'bank_tran_id']
    column_filters = ['status', 'currency', 'card_type']
    can_create = False
    can_edit = False


class ProfileSetUpAdminForm(ModelView):
    form = ProfileSetUpForm
    column_list = ['full_name', 'govt_reg', 'current_position', 'college', 'sex', 'phone']
    column_labels = {
        'full_name': 'Doctor Name',
        'govt_reg': 'BMDC / Reg No.',
        'current_position': 'Designation & Workplace',
        'college': 'Medical College',
        'sex': 'Gender',
        'phone': 'Contact Number'
    }
    can_create = False
    column_searchable_list = ['full_name', 'govt_reg', 'college']
    column_filters = ['sex']
