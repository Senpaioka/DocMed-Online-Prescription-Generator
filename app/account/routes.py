from flask import request, render_template, redirect, url_for, flash, Blueprint
from app.app import db
from app.account.forms import RegistrationForm, LoginForm, UpdateRegistrationForm 
from app.account.models import RegistrationModel
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email
from sqlalchemy.exc import IntegrityError
from flask_login import login_user, login_required, logout_user, current_user


accounts = Blueprint('accounts', __name__, template_folder='templates')


# registration page
@accounts.route('/registration', methods=['GET', 'POST'])
def registration_page():

    form = RegistrationForm()

    if request.method == "POST":

        if form.validate_on_submit():

            username = form.username.data
            email = form.email.data

            # validate email
            email_info = validate_email(email, check_deliverability=True)
            safe_email = email_info.normalized

            password = form.password.data
            gender = form.gender.data

            # alternative:
            # username = request.form.get('username')
            # email = request.form.get('email')
            # password = request.form.get('password')
            # confirm_password = request.form.get('confirm_password')
            # gender = request.form.get('gender')

            hashed_password = generate_password_hash(password)

            new_user = RegistrationModel(
                username = username,
                email = safe_email,
                password = hashed_password,
                gender = gender
            )

            new_user.is_active = True
            new_user.is_admin = False

            db.session.add(new_user)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Username already exists. Please choose a different one.", "error")
                return redirect(url_for('accounts.registration_page')) 

            flash('Account created successfully!', 'success')
            return redirect(url_for('home.home_page'))

        else:
            flash('Something went wrong!', 'error')
        

    context = {
        'form': form,
    }

    return render_template('account/registration.html', **context)






# login page
@accounts.route('/login', methods=['GET', 'POST'])
def login_page():

    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            username = form.username.data
            password = form.password.data

            # getting user
            user = RegistrationModel.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                flash('Login Successful', 'success')
                return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid ))

            else:
                flash('Invalid username or password', 'error')
                return redirect(url_for('accounts.login_page'))
    
    context = {
        'form': form,
    }    
    return render_template('account/login.html', **context)











# logout
@accounts.route('/logout')
@login_required
def logout_view():
    logout_user()
    flash('Logout Successful', 'success')
    return redirect(url_for('accounts.login_page'))









# update registration credentials
@accounts.route('/update/<int:uid>', methods=['GET', 'POST'])
@login_required
def registration_update_page(uid):

    # getting user existing data
    get_data = RegistrationModel.query.get(uid)

    if not get_data:
        flash("User data not found", "error")
        return redirect(url_for('accounts.login_page'))
    
    # prepopulated data
    form = UpdateRegistrationForm(obj=get_data)
    
    if request.method == "POST":

        if form.validate_on_submit():
            username = form.username.data
            email = form.email.data
            # validate email
            email_info = validate_email(email, check_deliverability=True)
            safe_email = email_info.normalized
            gender = form.gender.data

            # making password change optional
            if form.new_password.data:
                password = form.new_password.data
                hashed_password = generate_password_hash(password)
                get_data.password = hashed_password

            get_data.username = username
            get_data.email = safe_email
            get_data.gender = gender

            # alternative
            # update_data = form.populate_obj(get_data)
            # db.session.commit()

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Username already exists. Please choose a different one.", "error")
                return redirect(url_for('accounts.registration_update_page', uid=current_user.uid ))

            flash('Account Updated successfully!', 'success')
            return redirect(url_for('home.home_page'))

        else:
            flash('Something went wrong!', 'error')
            return redirect(url_for('accounts.registration_update_page', uid=current_user.uid ))


    context = {
        'form': form,
    }

    return render_template('account/update.html', **context)