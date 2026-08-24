from flask import request, render_template, redirect, url_for, flash, Blueprint, current_app
from app.extensions import db
from werkzeug.utils import secure_filename
import os
from app.modules.dashboard.forms import ProfileSetUpForm, UpdateProfileSetUpForm
from app.modules.dashboard.models import ProfileSetupModel
from app.modules.account.models import RegistrationModel
from app.modules.pdf.models import PrescriptionModel
from app.modules.search.forms import SearchForm
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
import time
from app.core.roles import doctor_required, role_required, UserRole


dashboard = Blueprint('dashboard', __name__, template_folder='templates')



# dashboard main page (Overview)
@dashboard.route('/user_home_page/<int:uid>')
@login_required
def dashboard_main_page(uid):
    user = RegistrationModel.query.get(uid)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('home.home_page'))

    is_profile_setup = user.profile_info

    form = SearchForm()

    context={
        'user': user,
        'setup_exists': is_profile_setup,
        'form': form,
    }

    # Separate patient and doctor dashboard templates
    if getattr(user, 'role', 'patient') == 'doctor' or user.is_admin:
        return render_template('dashboard/dashboard.html', **context)
    else:
        return render_template('patient-dashboard/dashboard.html', **context)


# patient verified doctors directory page
@dashboard.route('/verified-doctors/<int:uid>')
@login_required
def verified_doctors_page(uid):
    user = RegistrationModel.query.get(uid)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('home.home_page'))

    # Query all verified and active doctors
    verified_doctors = RegistrationModel.query.filter(
        RegistrationModel.role == 'doctor',
        RegistrationModel.verified_doctor == True,
        RegistrationModel.is_active == True
    ).all()

    context = {
        'user': user,
        'verified_doctors': verified_doctors,
    }

    return render_template('patient-dashboard/verified_doctors.html', **context)
















# setup page
@dashboard.route('/setup/<int:uid>', methods=['GET', 'POST'])
@login_required
@doctor_required
def setup_page(uid):
    
    form = ProfileSetUpForm()

    get_user = RegistrationModel.query.get(uid).get_id()

    if request.method == 'POST':
        if form.validate_on_submit():
            full_name = form.full_name.data
            birth_date = form.birth_date.data
            gender = form.sex.data
            tags = form.achievement.data
            phone = form.phone.data

            college = form.college.data
            university = form.higher_degree.data
            course = form.course.data
            extra_info = form.extra.data

            position = form.current_position.data
            govt_reg = form.govt_reg.data
            sign = form.signature.data
            office = form.office.data

            # image processing
            if sign:
                signature_image_name = secure_filename(sign.filename)
                # unique_filename
                timestamp = int(time.time())
                unique_filename = f"{timestamp}_{signature_image_name}"
                # image saving location
                upload_folder = current_app.config['UPLOAD_FOLDER']
                file_path = os.path.join(upload_folder, unique_filename).replace("\\", "/")
                sign.save(file_path)
                

            create_profile = ProfileSetupModel(
                user_id = get_user,
                full_name = full_name,
                birth_date = birth_date,
                sex = gender,
                achievement = tags,
                phone = phone,
                college = college,
                higher_degree = university,
                course = course,
                extra = extra_info,
                current_position = position,
                govt_reg = govt_reg,
                office = office,
                # saving img only name
                signature = unique_filename,
            )

            db.session.add(create_profile)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Something Went Wrong", "error")
                return redirect(url_for('dashboard.setup_page', uid=current_user.uid))

            flash('Profile Setup done successfully!', 'success')
            return redirect(url_for('dashboard.profile_page', uid=current_user.uid))

    context = {
        'form': form,
    }
    return render_template('dashboard/setup.html', **context)








@dashboard.route('/update_info/<int:uid>', methods=['GET', 'POST'])
@login_required
@doctor_required
def update_profile_info(uid):
    # getting user data    
    get_info = ProfileSetupModel.query.filter_by(user_id=uid).first()
    if not get_info:
        flash("Profile information not found. Please set up your profile.", "error")
        return redirect(url_for('dashboard.setup_page', uid=uid))

    # form
    form = UpdateProfileSetUpForm(obj=get_info)

    if request.method == 'POST':

        if form.validate_on_submit():
            get_info.full_name = form.full_name.data
            get_info.birth_date = form.birth_date.data
            get_info.sex = form.sex.data
            get_info.achievement = form.achievement.data
            get_info.phone = form.phone.data
            get_info.college = form.college.data
            get_info.higher_degree = form.higher_degree.data
            get_info.course = form.course.data
            get_info.extra = form.extra.data
            get_info.current_position = form.current_position.data
            get_info.govt_reg = form.govt_reg.data
            get_info.office = form.office.data

            sign = form.signature.data

            if sign and hasattr(sign, 'filename') and sign.filename:
                signature_image_name = secure_filename(sign.filename)
                timestamp = int(time.time())
                unique_filename = f"{timestamp}_{signature_image_name}"
                upload_folder = current_app.config['UPLOAD_FOLDER']
                file_path = os.path.join(upload_folder, unique_filename).replace("\\", "/")
                sign.save(file_path)
                get_info.signature = unique_filename


            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Something Went Wrong", "error")
                return redirect(url_for('dashboard.update_profile_info', uid=current_user.uid)) 

            flash('Profile Information Updated successfully!', 'success')
            return redirect(url_for('dashboard.profile_page', uid=current_user.uid))

            
    context = {
        'form': form,
        'data': get_info,
    }
    return render_template('dashboard/update.html', **context)







@dashboard.route('/profile_page/<int:uid>')
@login_required
def profile_page(uid):

    get_user = RegistrationModel.query.get(uid)
    if not get_user:
        flash("User not found.", "error")
        return redirect(url_for('home.home_page'))

    get_user_info = ProfileSetupModel.query.filter_by(user_id=uid).first()

    context = {
        'user': get_user,
        'info': get_user_info,
    }
    return render_template('dashboard/profile.html', **context)






@dashboard.route('/history/<int:uid>')
@login_required
def history_page(uid):
    # Get the current page from URL, default is 1
    get_page = request.args.get('page', 1, type=int) 
    # Number of items per page
    per_page = 25 

    user = RegistrationModel.query.get(uid)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('home.home_page'))

    # If doctor/admin, filter by doc_id. If patient, filter by patient_name or patient prescriptions
    is_doctor_user = getattr(user, 'role', 'patient') == 'doctor' or user.is_admin
    if is_doctor_user:
        paged_history = PrescriptionModel.query.filter_by(doc_id=uid).order_by(PrescriptionModel.created_at.desc()).paginate(page=get_page, per_page=per_page, error_out=False)
        is_history = user.prescription
    else:
        # Patient sees prescriptions addressed to their username/name
        paged_history = PrescriptionModel.query.filter(
            PrescriptionModel.patient_name.ilike(f"%{user.username}%")
        ).order_by(PrescriptionModel.created_at.desc()).paginate(page=get_page, per_page=per_page, error_out=False)
        is_history = paged_history.items
    
    context = {
        'user': user,
        'info': paged_history,
        'history_exists': is_history,
    }
    if request.headers.get('HX-Request'):
        if is_doctor_user:
            return render_template('dashboard/_history_list.html', **context)
        return render_template('patient-dashboard/_history_list.html', **context)

    if is_doctor_user:
        return render_template('dashboard/history.html', **context)
    return render_template('patient-dashboard/history.html', **context)








@dashboard.route('/template/<int:uid>')
@login_required
@doctor_required
def pdf_template_preview(uid):
    user = RegistrationModel.query.get(uid)
    if not user or not user.profile_info:
        flash("Please complete your doctor profile setup first to view your template.", "error")
        return redirect(url_for('dashboard.setup_page', uid=uid))

    get_doctor_info = user.profile_info

    context = {
        'doctor_info': get_doctor_info,
    }

    return render_template('dashboard/preview.html', **context)





