from datetime import datetime
from flask import request, render_template, redirect, url_for, flash, Blueprint
from app.extensions import db
from app.modules.account.forms import (
    RegistrationForm,
    LoginForm,
    UpdateRegistrationForm,
    VerifyOtpForm,
    ResendOtpForm,
    ForgotPasswordForm,
    ResetPasswordForm
)
from app.modules.account.models import RegistrationModel
from app.core.email_service import send_verification_otp, send_welcome_email, send_password_reset_email
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email
from sqlalchemy.exc import IntegrityError
from flask_login import login_user, login_required, logout_user, current_user


accounts = Blueprint('accounts', __name__, template_folder='templates')




# check username availability (HTMX)
@accounts.route('/check-username', methods=['POST'])
def check_username():
    username = request.form.get('username', '').strip()
    if not username:
        return ''
    if len(username) < 2:
        return '<span class="text-danger small"><i class="fa fa-times-circle"></i> Username must be at least 2 characters</span>'
    
    existing = RegistrationModel.query.filter_by(username=username).first()
    if existing:
        return '<span class="text-danger small"><i class="fa fa-times-circle"></i> Username is already taken</span>'
    return '<span class="text-success small"><i class="fa fa-check-circle"></i> Username is available</span>'


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

            # Check if email is already registered
            existing_email = RegistrationModel.query.filter(RegistrationModel.email.ilike(safe_email)).first()
            if existing_email:
                if not existing_email.is_verified:
                    # User started registration earlier but did not verify
                    send_verification_otp(existing_email)
                    flash('An unverified account with this email exists. A new OTP has been sent!', 'info')
                    return redirect(url_for('accounts.verify_otp', user_id=existing_email.uid))
                else:
                    flash('Email address is already in use. Please sign in or use another email.', 'error')
                    return redirect(url_for('accounts.registration_page'))

            # Check if username is already registered
            existing_user = RegistrationModel.query.filter_by(username=username).first()
            if existing_user:
                flash('Username is already taken. Please choose a different one.', 'error')
                return redirect(url_for('accounts.registration_page'))

            password = form.password.data
            gender = form.gender.data
            role = getattr(form, 'role', None)
            selected_role = role.data if role and role.data else 'patient'

            hashed_password = generate_password_hash(password)

            new_user = RegistrationModel(
                username = username,
                email = safe_email,
                password = hashed_password,
                gender = gender,
                role = selected_role
            )

            new_user.is_active = True
            new_user.is_verified = False
            new_user.is_admin = (selected_role == 'admin')

            db.session.add(new_user)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Username or Email already exists. Please choose a different one.", "error")
                return redirect(url_for('accounts.registration_page')) 


            # Send OTP verification email
            email_sent = send_verification_otp(new_user)
            if email_sent:
                flash('Account created! A 6-digit OTP verification code was sent to your email.', 'success')
            else:
                flash('Account created, but we could not deliver the verification email right now. You can request a resend.', 'error')

            return redirect(url_for('accounts.verify_otp', user_id=new_user.uid))

        else:
            flash('Please correct the errors in the form.', 'error')
        

    context = {
        'form': form,
    }

    return render_template('account/registration.html', **context)


# OTP Verification Page
@accounts.route('/verify-otp/<int:user_id>', methods=['GET', 'POST'])
def verify_otp(user_id):
    user = RegistrationModel.query.get_or_404(user_id)

    if user.is_verified:
        flash('Your email is already verified! Please sign in.', 'info')
        return redirect(url_for('accounts.login_page'))

    verify_form = VerifyOtpForm()
    resend_form = ResendOtpForm()

    if verify_form.validate_on_submit():
        submitted_otp = verify_form.otp.data.strip()

        if not user.otp_code:
            flash('No verification code active. Please request a new one.', 'error')
            return redirect(url_for('accounts.verify_otp', user_id=user.uid))

        if user.otp_expiry and datetime.now() > user.otp_expiry:
            flash('Verification code has expired. Please request a new OTP.', 'error')
            return redirect(url_for('accounts.verify_otp', user_id=user.uid))

        if user.otp_code == submitted_otp:
            user.is_verified = True
            user.otp_code = None
            user.otp_expiry = None
            db.session.commit()

            # Send role-based welcome email (Doctor vs Patient)
            dashboard_url = url_for('dashboard.dashboard_main_page', uid=user.uid, _external=True)
            send_welcome_email(user, dashboard_url=dashboard_url)

            # Automatically log the user in after successful verification
            login_user(user)
            flash('Email verified successfully! Welcome to DocMed.', 'success')
            return redirect(url_for('dashboard.dashboard_main_page', uid=user.uid))
        else:
            flash('Invalid OTP code. Please check your email and try again.', 'error')


    context = {
        'user': user,
        'verify_form': verify_form,
        'resend_form': resend_form
    }
    return render_template('account/verify_otp.html', **context)


# Resend OTP route
@accounts.route('/resend-otp/<int:user_id>', methods=['POST'])
def resend_otp(user_id):
    user = RegistrationModel.query.get_or_404(user_id)

    if user.is_verified:
        flash('Your email is already verified. Please sign in.', 'info')
        return redirect(url_for('accounts.login_page'))

    resend_form = ResendOtpForm()
    if resend_form.validate_on_submit():
        sent = send_verification_otp(user)
        if sent:
            flash('A fresh OTP code has been sent to your email!', 'success')
        else:
            flash('Failed to resend email. Please check your network or try again later.', 'error')
    
    return redirect(url_for('accounts.verify_otp', user_id=user.uid))


# login page
@accounts.route('/login', methods=['GET', 'POST'])
def login_page():

    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data.strip()
            password = form.password.data

            # getting user by email (case-insensitive)
            user = RegistrationModel.query.filter(RegistrationModel.email.ilike(email)).first()
            if user and check_password_hash(user.password, password):
                if not getattr(user, 'is_verified', True):
                    # Send a fresh OTP and redirect to verification page
                    send_verification_otp(user)
                    flash('Your email is not verified yet. A new verification OTP was sent to your email.', 'error')
                    return redirect(url_for('accounts.verify_otp', user_id=user.uid))

                login_user(user)
                flash('Login Successful', 'success')
                
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                
                if getattr(user, 'is_admin', False) or getattr(user, 'role', '') == 'admin':
                    return redirect(url_for('admin.index'))

                return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

            else:
                flash('Invalid email or password', 'error')
                return redirect(url_for('accounts.login_page', next=request.args.get('next')))
    
    context = {
        'form': form,
    }    
    return render_template('account/login.html', **context)



# forgot password
@accounts.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        user = RegistrationModel.query.filter(RegistrationModel.email.ilike(email)).first()
        if user:
            token = user.get_reset_password_token(expires_sec=1800)
            reset_url = url_for('accounts.reset_password', token=token, _external=True)
            sent = send_password_reset_email(user, reset_url=reset_url, expiry_minutes=30)
            if sent:
                flash('Password reset instructions have been sent to your email address.', 'success')
            else:
                flash('Failed to deliver password reset email. Please try again later.', 'error')
        else:
            flash('If an account exists with this email, you will receive password reset instructions shortly.', 'info')
        return redirect(url_for('accounts.login_page'))

    context = {
        'form': form
    }
    return render_template('account/forgot_password.html', **context)


# reset password with token
@accounts.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

    user = RegistrationModel.verify_reset_password_token(token, expires_sec=1800)
    if not user:
        flash('The password reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('accounts.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        new_password = form.password.data
        user.password = generate_password_hash(new_password)
        user.is_verified = True
        db.session.commit()

        flash('Your password has been reset successfully! You can now sign in with your new password.', 'success')
        return redirect(url_for('accounts.login_page'))

    context = {
        'form': form,
        'user': user
    }
    return render_template('account/reset_password.html', **context)


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

            # Check if email is used by another user
            duplicate_email = RegistrationModel.query.filter(RegistrationModel.email.ilike(safe_email), RegistrationModel.uid != uid).first()
            if duplicate_email:
                flash('Email address is already in use by another account.', 'error')
                return redirect(url_for('accounts.registration_update_page', uid=current_user.uid))

            # Check if username is used by another user
            duplicate_user = RegistrationModel.query.filter(RegistrationModel.username == username, RegistrationModel.uid != uid).first()
            if duplicate_user:
                flash('Username is already taken by another account.', 'error')
                return redirect(url_for('accounts.registration_update_page', uid=current_user.uid))

            # making password change optional
            if form.new_password.data:
                password = form.new_password.data
                hashed_password = generate_password_hash(password)
                get_data.password = hashed_password

            get_data.username = username
            get_data.email = safe_email
            get_data.gender = gender

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Username or Email already exists. Please choose a different one.", "error")
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