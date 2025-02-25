from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, SubmitField, FileField
from wtforms.validators import DataRequired, Length, Optional
from flask_wtf.file import FileField, FileAllowed, FileRequired
from flask_admin.contrib.sqla import ModelView
import os
from werkzeug.utils import secure_filename
from flask import url_for
from flask import current_app


class ProfileSetUpForm(FlaskForm):

    full_name = StringField('full_name', validators=[DataRequired(), Length(min=5,max=120 )])
    birth_date = DateField('birth_date', validators=[DataRequired()])
    sex = SelectField('gender', choices=[
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other')

], validators=[DataRequired()])
    achievement = StringField('achieve',validators=[DataRequired()])
    phone = StringField('phone', validators=[Optional()])
    college = StringField('college', validators=[DataRequired()])
    higher_degree = StringField('higher_degree', validators=[Optional()])
    course = StringField('course', validators=[Optional()])
    extra = StringField('extra', validators=[Optional()])
    current_position = StringField('current_position', validators=[DataRequired()])
    govt_reg = StringField('reg_no', validators=[DataRequired()])
    office = StringField('address', validators=[Optional()])
    signature = FileField('sign', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'svg'], 'Images only!'), FileRequired()])

    submit = SubmitField('Submit')






class UpdateProfileSetUpForm(FlaskForm):

    full_name = StringField('full_name', validators=[DataRequired(), Length(min=5,max=120 )])
    birth_date = DateField('birth_date', validators=[DataRequired()])
    sex = SelectField('gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    achievement = StringField('achieve',validators=[DataRequired()])
    phone = StringField('phone', validators=[Optional()])
    college = StringField('college', validators=[DataRequired()])
    higher_degree = StringField('higher_degree', validators=[Optional()])
    course = StringField('course', validators=[Optional()])
    extra = StringField('extra', validators=[Optional()])
    current_position = StringField('current_position', validators=[DataRequired()])
    govt_reg = StringField('reg_no', validators=[DataRequired()])
    office = StringField('address', validators=[Optional()])
    signature = FileField('sign', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'svg'], 'Images only!'), Optional()])

    submit = SubmitField('Update Info')





####### Admin Panel ########

class ProfileSetUpAdminForm(ModelView):

    form = ProfileSetUpForm

    # columns show in admin panel  
    column_list = ['full_name', 'achievement', 'current_position', 'govt_reg', 'sex']
    # disabling create update profile info
    can_create = False

    column_searchable_list = ['full_name']

    # sign saving method from admin-panel
    # def on_model_change(self, form, model, is_created):
    #     """Save uploaded signature file correctly"""
    #     if form.signature.data:
    #         signature_image_name = secure_filename(form.signature.data.filename)
    #         print(signature_image_name)

    #         # Define the actual file system path (absolute path)
    #         file_path = os.path.join(current_app.root_path, 'static', 'uploads', signature_image_name)
            
    #         # Save the file to the correct directory
    #         form.signature.data.save(file_path)

    #         # Store the relative path (so it works with `url_for`)
    #         model.signature = f'uploads/{signature_image_name}'
