from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp
from werkzeug.security import generate_password_hash
from flask_admin.contrib.sqla import ModelView
from app.core.roles import UserRole

# Password complexity regex: at least 8 characters, 1 uppercase, 1 lowercase, 1 digit, 1 special character
PASSWORD_REGEX = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|`~]).{8,}$'
PASSWORD_MESSAGE = (
    'Password must be at least 8 characters long and contain at least one uppercase letter, '
    'one lowercase letter, one number, and one special character.'
)


######## Front End #########
class RegistrationForm(FlaskForm):

    username = StringField('username', validators=[DataRequired(), Length(min=2, max=60)])
    email = StringField('email', validators=[DataRequired(), Email()])
    password = PasswordField('password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters.'),
        Regexp(PASSWORD_REGEX, message=PASSWORD_MESSAGE)
    ])
    confirm_password = PasswordField('confirm_password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    gender = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], validators=[DataRequired(message="Please select your gender.")])
    role = SelectField('role', choices=[
        (UserRole.PATIENT, 'Patient'),
        (UserRole.DOCTOR, 'Doctor')
    ], default=UserRole.PATIENT, validators=[DataRequired(message="Please select your role.")])

    submit = SubmitField('Register')




class LoginForm(FlaskForm):

    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])

    login = SubmitField('Login')


class UpdateRegistrationForm(FlaskForm):

    username = StringField('username', validators=[DataRequired(), Length(min=2, max=60)])
    email = StringField('email', validators=[DataRequired(), Email()])
    
    new_password = PasswordField('new_password', validators=[
        Optional(),
        Length(min=8, message='Password must be at least 8 characters.'),
        Regexp(PASSWORD_REGEX, message=PASSWORD_MESSAGE)
    ])
    confirm_password = PasswordField('confirm_password', validators=[
        Optional(),
        EqualTo('new_password', message='Passwords must match')
    ])
    gender = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], validators=[DataRequired(message="Please select your gender.")])

    update = SubmitField('Update')








class VerifyOtpForm(FlaskForm):
    otp = StringField('Verification Code', validators=[
        DataRequired(message='Please enter the 6-digit code.'),
        Length(min=6, max=6, message='OTP must be exactly 6 digits.')
    ])
    submit = SubmitField('Verify Code')


class ResendOtpForm(FlaskForm):
    submit = SubmitField('Resend Verification Code')


######## Admin Panel #########
class AdminPanelRegistration(FlaskForm):

    username = StringField('username', validators=[DataRequired(), Length(min=2, max=60)])
    email = StringField('email', validators=[DataRequired(), Email()])
    
    new_password = PasswordField('new_password', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('confirm_password', validators=[Optional(), EqualTo('new_password',  message='Passwords must match')]) # checking both password matched
    gender = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], validators=[DataRequired(message="Please select your gender.")])
    role = SelectField('role', choices=UserRole.CHOICES, default=UserRole.PATIENT, validators=[DataRequired()])

    is_verified = BooleanField('is_verified', default=True)
    is_active = BooleanField('is_active', default=True)
    is_admin = BooleanField('is_admin', default=False)

    update = SubmitField('Save')




# ModelForm for Admin Panel
class RegistrationAdminForm(ModelView):

    form = AdminPanelRegistration
    # columns show in admin panel  
    column_list = ['username', 'email', 'role', 'gender', 'is_verified', 'is_active', 'is_admin', 'created_at']
    # column filters
    column_filters = ['role', 'is_verified', 'is_active', 'is_admin', 'gender']
    # column to fill in admin form
    form_columns = ['username', 'email', 'new_password', 'confirm_password', 'role', 'gender', 'is_verified', 'is_active', 'is_admin']

    column_searchable_list = ['username', 'email']

    def on_model_change(self, form, model, is_created):
        """Hash password before storing it in the database and sync is_admin with role"""
        if form.new_password.data: 
            model.password = generate_password_hash(form.new_password.data)
        if form.role.data == UserRole.ADMIN:
            model.is_admin = True
        elif form.is_admin.data:
            model.role = UserRole.ADMIN
