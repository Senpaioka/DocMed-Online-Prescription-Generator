from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from werkzeug.security import generate_password_hash
from flask_admin.contrib.sqla import ModelView


######## Front End #########
class RegistrationForm(FlaskForm):

    username = StringField('username', validators=[DataRequired(), Length(min=2, max=60)])
    email = StringField('email', validators=[DataRequired(), Email()])
    password = PasswordField('password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('confirm_password', validators=[DataRequired(), EqualTo('password',  message='Passwords must match')]) # checking both password matched
    gender = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    validators=[DataRequired(message="Please select your gender.")]

    submit = SubmitField('Register')




class LoginForm(FlaskForm):

    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])

    login = SubmitField('Login')


class UpdateRegistrationForm(FlaskForm):

    username = StringField('username', validators=[DataRequired(), Length(min=2, max=60)])
    email = StringField('email', validators=[DataRequired(), Email()])
    
    new_password = PasswordField('new_password', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('confirm_password', validators=[Optional(), EqualTo('new_password',  message='Passwords must match')]) # checking both password matched
    gender = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    validators=[DataRequired(message="Please select your gender.")]

    # is_active = BooleanField('is_active')

    update = SubmitField('Update')







######## Admin Panel #########
class AdminPanelRegistration(FlaskForm):

    username = StringField('username', validators=[DataRequired(), Length(min=2, max=60)])
    email = StringField('email', validators=[DataRequired(), Email()])
    
    new_password = PasswordField('new_password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('confirm_password', validators=[DataRequired(), EqualTo('new_password',  message='Passwords must match')]) # checking both password matched
    gender = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    validators=[DataRequired(message="Please select your gender.")]

    is_active = BooleanField('is_active')
    is_admin = BooleanField('is_active')

    update = SubmitField('ADD')




# ModelForm for Admin Panel
class RegistrationAdminForm(ModelView):

    form = AdminPanelRegistration
    # columns show in admin panel  
    column_list = ['username', 'email', 'gender', 'is_active', 'is_admin']
    # column to fill
    form_columns = ['username', 'email', 'password', 'confirm_password', 'gender' ]

    column_searchable_list = ['username', 'email']


    def on_model_change(self, form, model, is_created):
        """Hash password before storing it in the database"""
        if form.new_password.data: 
            model.new_password = generate_password_hash(form.new_password.data)
        