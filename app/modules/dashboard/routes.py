from flask import request, render_template, redirect, url_for, flash, Blueprint, current_app, Response, stream_with_context, jsonify
from app.extensions import db
from werkzeug.utils import secure_filename
import os
import queue
from app.modules.dashboard.forms import ProfileSetUpForm, UpdateProfileSetUpForm
from app.modules.dashboard.models import ProfileSetupModel, AppointmentModel, NotificationModel
from app.modules.account.models import RegistrationModel
from app.modules.pdf.models import PrescriptionModel
from app.modules.search.forms import SearchForm
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
import time
from app.core.roles import doctor_required, role_required, UserRole
from app.core.sse import sse_manager
from app.core.notification_service import (
    notify_patient_appointment_confirmed,
    notify_patient_appointment_rejected,
    notify_patient_appointment_cancelled,
    notify_doctor_new_appointment
)


dashboard = Blueprint('dashboard', __name__, template_folder='templates')


# ==========================================
# SSE NOTIFICATION STREAM & API ENDPOINTS
# ==========================================

@dashboard.route('/notifications/stream')
@login_required
def notification_stream():
    """
    Server-Sent Events (SSE) streaming endpoint for real-time notifications.
    Streams instant notifications to the logged-in user.
    """
    def event_stream():
        user_id = current_user.uid
        q = sse_manager.subscribe(user_id)
        
        # Initial connect message with current unread count
        initial_unread = NotificationModel.query.filter_by(user_id=user_id, is_read=False).count()
        yield sse_manager.format_sse(
            event_type='connected',
            data={'status': 'connected', 'user_id': user_id, 'unread_count': initial_unread}
        )

        try:
            while True:
                try:
                    # Wait for message in queue (timeout in 15 seconds)
                    msg = q.get(timeout=15)
                    yield msg
                except queue.Empty:
                    # Periodic heartbeat to keep connection alive through proxies
                    yield sse_manager.format_ping()
        except GeneratorExit:
            pass
        finally:
            sse_manager.unsubscribe(user_id, q)

    response = Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache, no-transform'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response


@dashboard.route('/notifications/api')
@login_required
def get_notifications_api():
    """Fetch user's recent notifications as JSON."""
    limit = request.args.get('limit', 20, type=int)
    notifications = NotificationModel.query.filter_by(user_id=current_user.uid)\
        .order_by(NotificationModel.created_at.desc()).limit(limit).all()
    unread_count = NotificationModel.query.filter_by(user_id=current_user.uid, is_read=False).count()
    return jsonify({
        'status': 'success',
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifications]
    })


@dashboard.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a single notification as read."""
    notification = NotificationModel.query.filter_by(id=notification_id, user_id=current_user.uid).first()
    if notification:
        notification.is_read = True
        db.session.commit()
    unread_count = NotificationModel.query.filter_by(user_id=current_user.uid, is_read=False).count()
    return jsonify({'status': 'success', 'unread_count': unread_count})


@dashboard.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications for the current user as read."""
    NotificationModel.query.filter_by(user_id=current_user.uid, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'success', 'unread_count': 0})


@dashboard.route('/patient-appointments-feed/<int:uid>')
@login_required
def patient_appointments_feed(uid):
    """Render appointment feed fragment for live SSE-triggered DOM updates."""
    if current_user.uid != uid and not current_user.is_admin:
        return "<p class='text-danger'>Unauthorized</p>", 403

    appointments = AppointmentModel.query.filter_by(patient_id=uid).order_by(AppointmentModel.created_at.desc()).all()
    return render_template('patient-dashboard/_appointments_feed.html', appointments=appointments)


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


# ==========================================
# APPOINTMENT MANAGEMENT SYSTEM
# ==========================================

# Patient: Request an appointment with a verified doctor
@dashboard.route('/appointment/request/<int:doctor_id>', methods=['POST'])
@login_required
def request_appointment(doctor_id):
    doctor = RegistrationModel.query.get_or_404(doctor_id)
    
    if doctor.role != 'doctor' or not doctor.verified_doctor:
        flash("Appointments can only be scheduled with verified doctors.", "error")
        return redirect(url_for('dashboard.verified_doctors_page', uid=current_user.uid))

    if current_user.uid == doctor_id:
        flash("You cannot book an appointment with yourself.", "warning")
        return redirect(url_for('dashboard.verified_doctors_page', uid=current_user.uid))

    patient_name = request.form.get('patient_name', '').strip() or current_user.username
    patient_email = request.form.get('patient_email', '').strip() or current_user.email
    patient_phone = request.form.get('patient_phone', '').strip()

    if not patient_phone:
        flash("Please provide your contact phone number to request an appointment.", "error")
        return redirect(url_for('dashboard.verified_doctors_page', uid=current_user.uid))

    new_appointment = AppointmentModel(
        patient_id=current_user.uid,
        doctor_id=doctor.uid,
        status='pending',
        patient_name=patient_name,
        patient_email=patient_email,
        patient_phone=patient_phone
    )

    try:
        db.session.add(new_appointment)
        db.session.commit()

        # Push real-time notification to doctor
        notify_doctor_new_appointment(new_appointment)

        flash(f"Appointment request submitted to Dr. {doctor.username}! The doctor will assign and schedule a date and time for you.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error booking appointment: {e}")
        flash("Failed to submit appointment request. Please try again.", "error")

    return redirect(url_for('dashboard.patient_appointments_page', uid=current_user.uid))


# Patient: View all appointments for the logged in patient
@dashboard.route('/my-appointments/<int:uid>')
@login_required
def patient_appointments_page(uid):
    if current_user.uid != uid and not current_user.is_admin:
        flash("Unauthorized access.", "error")
        return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

    user = RegistrationModel.query.get_or_404(uid)
    appointments = AppointmentModel.query.filter_by(patient_id=uid).order_by(AppointmentModel.created_at.desc()).all()

    context = {
        'user': user,
        'appointments': appointments,
    }
    return render_template('patient-dashboard/appointments.html', **context)


# Doctor: View doctor appointment management dashboard
@dashboard.route('/doctor-appointments/<int:uid>')
@login_required
@doctor_required
def doctor_appointments_page(uid):
    if current_user.uid != uid and not current_user.is_admin:
        flash("Unauthorized access.", "error")
        return redirect(url_for('dashboard.dashboard_main_page', uid=current_user.uid))

    user = RegistrationModel.query.get_or_404(uid)
    status_filter = request.args.get('status', 'all')

    query = AppointmentModel.query.filter_by(doctor_id=uid)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    appointments = query.order_by(AppointmentModel.created_at.desc()).all()

    pending_count = AppointmentModel.query.filter_by(doctor_id=uid, status='pending').count()
    confirmed_count = AppointmentModel.query.filter_by(doctor_id=uid, status='confirmed').count()
    completed_count = AppointmentModel.query.filter_by(doctor_id=uid, status='completed').count()
    total_count = AppointmentModel.query.filter_by(doctor_id=uid).count()

    context = {
        'user': user,
        'appointments': appointments,
        'active_filter': status_filter,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'completed_count': completed_count,
        'total_count': total_count,
    }
    return render_template('dashboard/doctor_appointments.html', **context)


# Doctor: Accept / Schedule appointment and notify patient by SSE & email
@dashboard.route('/doctor/appointment/confirm/<int:appointment_id>', methods=['POST'])
@login_required
@doctor_required
def confirm_appointment(appointment_id):
    appointment = AppointmentModel.query.get_or_404(appointment_id)

    if appointment.doctor_id != current_user.uid and not current_user.is_admin:
        flash("You do not have permission to manage this appointment.", "error")
        return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))

    scheduled_date_str = request.form.get('scheduled_date', '').strip()
    scheduled_time = request.form.get('scheduled_time', '').strip()
    doctor_notes = request.form.get('doctor_notes', '').strip()

    if not scheduled_date_str or not scheduled_time:
        flash("Please specify both a confirmed appointment date and time.", "error")
        return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))

    from datetime import datetime as dt
    try:
        scheduled_date = dt.strptime(scheduled_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid scheduled date format.", "error")
        return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))

    appointment.status = 'confirmed'
    appointment.scheduled_date = scheduled_date
    appointment.scheduled_time = scheduled_time
    appointment.doctor_notes = doctor_notes
    db.session.commit()

    # Dispatch real-time SSE notification to patient
    notify_patient_appointment_confirmed(appointment)

    # Dispatch email notification to patient
    from app.core.email_service import send_appointment_confirmed_email
    patient = RegistrationModel.query.get(appointment.patient_id)
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doctor_profile = ProfileSetupModel.query.filter_by(user_id=doctor.uid).first()
    
    patient_dashboard_url = url_for('dashboard.patient_appointments_page', uid=patient.uid, _external=True)
    email_sent = send_appointment_confirmed_email(
        appointment=appointment,
        patient=patient,
        doctor=doctor,
        doctor_profile=doctor_profile,
        patient_dashboard_url=patient_dashboard_url
    )

    if email_sent:
        flash(f"Appointment with {appointment.patient_name} confirmed for {scheduled_date_str} at {scheduled_time}. Email notification sent to patient!", "success")
    else:
        flash(f"Appointment confirmed, but notification email could not be sent.", "warning")

    return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))


# Doctor: Reject a pending appointment request
@dashboard.route('/doctor/appointment/reject/<int:appointment_id>', methods=['POST'])
@login_required
@doctor_required
def reject_appointment(appointment_id):
    appointment = AppointmentModel.query.get_or_404(appointment_id)

    if appointment.doctor_id != current_user.uid and not current_user.is_admin:
        flash("You do not have permission to manage this appointment.", "error")
        return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))

    rejection_reason = request.form.get('rejection_reason', '').strip()
    appointment.status = 'rejected'
    if rejection_reason:
        appointment.doctor_notes = rejection_reason
    db.session.commit()

    # Dispatch real-time SSE notification to patient
    notify_patient_appointment_rejected(appointment, reason=rejection_reason)

    # Dispatch rejection email to patient
    from app.core.email_service import send_appointment_cancelled_email
    patient = RegistrationModel.query.get(appointment.patient_id)
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doctor_profile = ProfileSetupModel.query.filter_by(user_id=doctor.uid).first()
    patient_dashboard_url = url_for('dashboard.verified_doctors_page', uid=patient.uid, _external=True)

    send_appointment_cancelled_email(
        appointment=appointment,
        patient=patient,
        doctor=doctor,
        doctor_profile=doctor_profile,
        reason=rejection_reason,
        patient_dashboard_url=patient_dashboard_url
    )

    flash(f"Appointment request from {appointment.patient_name} has been rejected. Notification email sent to patient.", "info")
    return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))


# Doctor: Cancel a previously scheduled/confirmed appointment
@dashboard.route('/doctor/appointment/cancel/<int:appointment_id>', methods=['POST'])
@login_required
@doctor_required
def cancel_appointment(appointment_id):
    appointment = AppointmentModel.query.get_or_404(appointment_id)

    if appointment.doctor_id != current_user.uid and not current_user.is_admin:
        flash("You do not have permission to cancel this appointment.", "error")
        return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))

    cancellation_reason = request.form.get('cancellation_reason', '').strip()
    appointment.status = 'cancelled'
    if cancellation_reason:
        appointment.doctor_notes = cancellation_reason
    db.session.commit()

    # Dispatch real-time SSE notification to patient
    notify_patient_appointment_cancelled(appointment, reason=cancellation_reason)

    # Dispatch cancellation email to patient
    from app.core.email_service import send_appointment_cancelled_email
    patient = RegistrationModel.query.get(appointment.patient_id)
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doctor_profile = ProfileSetupModel.query.filter_by(user_id=doctor.uid).first()
    patient_dashboard_url = url_for('dashboard.verified_doctors_page', uid=patient.uid, _external=True)

    send_appointment_cancelled_email(
        appointment=appointment,
        patient=patient,
        doctor=doctor,
        doctor_profile=doctor_profile,
        reason=cancellation_reason,
        patient_dashboard_url=patient_dashboard_url
    )

    flash(f"Appointment with {appointment.patient_name} has been cancelled. An email has been sent to notify the patient.", "info")
    return redirect(url_for('dashboard.doctor_appointments_page', uid=current_user.uid))


















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





