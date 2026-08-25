from flask import request, render_template, redirect, url_for, flash, Blueprint, current_app, Response, stream_with_context, jsonify
from app.extensions import db
from werkzeug.utils import secure_filename
import os
import queue
from app.modules.dashboard.forms import ProfileSetUpForm, UpdateProfileSetUpForm
from app.modules.dashboard.models import ProfileSetupModel, AppointmentModel, NotificationModel, PaymentTransactionModel
from app.modules.account.models import RegistrationModel
from app.modules.pdf.models import PrescriptionModel
from app.modules.search.forms import SearchForm
from flask_login import login_required, current_user, login_user
from sqlalchemy.exc import IntegrityError
import time
from datetime import datetime
from app.core.roles import doctor_required, role_required, UserRole
from app.core.sse import sse_manager
from app.core.notification_service import (
    notify_patient_appointment_confirmed,
    notify_patient_appointment_rejected,
    notify_patient_appointment_cancelled,
    notify_doctor_new_appointment,
    notify_payment_success
)
from app.core.sslcommerz import initiate_sslcommerz_payment, validate_sslcommerz_payment


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

    doc_fee = 1000.0
    if doctor.profile_info and doctor.profile_info.consultation_fee:
        doc_fee = float(doctor.profile_info.consultation_fee)

    new_appointment = AppointmentModel(
        patient_id=current_user.uid,
        doctor_id=doctor.uid,
        status='pending',
        patient_name=patient_name,
        patient_email=patient_email,
        patient_phone=patient_phone,
        fee_amount=doc_fee
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
    fee_amount_str = request.form.get('fee_amount', '').strip()

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
    if fee_amount_str:
        try:
            appointment.fee_amount = max(0.0, float(fee_amount_str))
        except ValueError:
            pass
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


# ==========================================
# SSLCOMMERZ PAYMENT GATEWAY ROUTES
# ==========================================

# Patient: Initiate SSLCommerz payment for an approved appointment
@dashboard.route('/appointment/pay/<int:appointment_id>', methods=['POST'])
@login_required
def pay_appointment_fee(appointment_id):
    appointment = AppointmentModel.query.get_or_404(appointment_id)

    if appointment.patient_id != current_user.uid and not current_user.is_admin:
        flash("Unauthorized access to this appointment payment.", "error")
        return redirect(url_for('dashboard.patient_appointments_page', uid=current_user.uid))

    if appointment.status not in ['confirmed', 'completed']:
        flash("Payment can only be initiated for confirmed or completed appointments.", "warning")
        return redirect(url_for('dashboard.patient_appointments_page', uid=current_user.uid))

    if appointment.payment_status == 'paid':
        flash("This consultation fee has already been paid.", "info")
        return redirect(url_for('dashboard.patient_appointments_page', uid=current_user.uid))

    # Fee amount: patient can specify or use appointment's fee_amount
    custom_amount_str = request.form.get('amount', '').strip()
    amount = 0.0
    if custom_amount_str:
        try:
            amount = float(custom_amount_str)
        except ValueError:
            amount = 0.0

    if amount <= 0:
        amount = appointment.fee_amount if (appointment.fee_amount and appointment.fee_amount > 0) else 1000.00

    # Save the fee amount to the appointment record
    appointment.fee_amount = amount
    db.session.commit()

    patient = RegistrationModel.query.get(appointment.patient_id)
    doctor = RegistrationModel.query.get(appointment.doctor_id)

    # Initiate session via SSLCommerz V4 API
    result = initiate_sslcommerz_payment(
        appointment=appointment,
        amount=amount,
        patient=patient,
        doctor=doctor
    )

    if result.get('status') == 'SUCCESS' and result.get('gateway_url'):
        return redirect(result['gateway_url'])
    else:
        error_msg = result.get('message', 'Failed to connect to SSLCommerz payment gateway.')
        flash(f"Payment gateway error: {error_msg}", "error")
        return redirect(url_for('dashboard.patient_appointments_page', uid=current_user.uid))


# SSLCommerz Payment Success Callback
@dashboard.route('/payment/success', methods=['GET', 'POST'])
def sslcommerz_success():
    data = request.form.to_dict() if request.method == 'POST' else request.args.to_dict()
    current_app.logger.info(f"SSLCommerz Success Callback received: {data}")

    val_id = data.get('val_id')
    tran_id = data.get('tran_id')
    amount_str = data.get('amount') or data.get('value_d') or '0.00'
    appointment_id_str = data.get('value_a')
    card_type = data.get('card_type', 'SSLCommerz')
    bank_tran_id = data.get('bank_tran_id', '')
    card_brand = data.get('card_brand', '')
    card_issuer = data.get('card_issuer', '')

    appointment = None
    if appointment_id_str:
        try:
            appointment = AppointmentModel.query.get(int(appointment_id_str))
        except (ValueError, TypeError):
            pass

    if not appointment and tran_id:
        appointment = AppointmentModel.query.filter_by(transaction_id=tran_id).first()

    # Validate transaction with SSLCommerz API
    validation_result = {}
    if val_id:
        validation_result = validate_sslcommerz_payment(val_id)
        current_app.logger.info(f"SSLCommerz Validation Result for val_id {val_id}: {validation_result}")

    if appointment:
        try:
            amount_val = float(validation_result.get('amount') or amount_str or appointment.fee_amount or 1000.0)
        except ValueError:
            amount_val = float(appointment.fee_amount or 1000.0)

        appointment.payment_status = 'paid'
        appointment.payment_amount = amount_val
        appointment.payment_method = card_type or validation_result.get('card_type', 'SSLCommerz')
        appointment.transaction_id = tran_id or validation_result.get('tran_id', appointment.transaction_id)
        appointment.bank_tran_id = bank_tran_id or validation_result.get('bank_tran_id', '')
        appointment.payment_date = datetime.now()

        # Update transaction record if exists
        txn = PaymentTransactionModel.query.filter_by(tran_id=appointment.transaction_id).first()
        if txn:
            txn.status = 'success'
            txn.val_id = val_id
            txn.amount = amount_val
            txn.card_type = appointment.payment_method
            txn.bank_tran_id = appointment.bank_tran_id
            txn.card_brand = card_brand
            txn.card_issuer = card_issuer
            import json
            txn.raw_response = json.dumps(validation_result or data)

        db.session.commit()

        # Re-authenticate patient session in case cross-origin POST from SSLCommerz dropped the session cookie
        patient = RegistrationModel.query.get(appointment.patient_id)
        if patient:
            login_user(patient, remember=True)

        # Dispatch real-time SSE notifications
        notify_payment_success(appointment, amount_val, appointment.transaction_id)

        flash(f"Payment of ৳{amount_val:.2f} for Appointment #{appointment.id} was completed successfully via {appointment.payment_method}!", "success")
        return redirect(url_for('dashboard.patient_appointments_page', uid=appointment.patient_id))

    flash("Payment processed successfully. Please check your appointments list.", "info")
    return redirect(url_for('dashboard.patient_appointments_page', uid=current_user.uid if current_user.is_authenticated else 1))


# SSLCommerz Payment Fail Callback
@dashboard.route('/payment/fail', methods=['GET', 'POST'])
def sslcommerz_fail():
    data = request.form.to_dict() if request.method == 'POST' else request.args.to_dict()
    current_app.logger.warning(f"SSLCommerz Fail Callback received: {data}")

    tran_id = data.get('tran_id')
    appointment_id_str = data.get('value_a')
    failed_reason = data.get('error', 'Payment transaction failed or was declined.')

    appointment = None
    if appointment_id_str:
        try:
            appointment = AppointmentModel.query.get(int(appointment_id_str))
        except (ValueError, TypeError):
            pass
    if not appointment and tran_id:
        appointment = AppointmentModel.query.filter_by(transaction_id=tran_id).first()

    if appointment:
        appointment.payment_status = 'failed'
        txn = PaymentTransactionModel.query.filter_by(tran_id=tran_id).first()
        if txn:
            txn.status = 'failed'
            import json
            txn.raw_response = json.dumps(data)
        db.session.commit()

        # Re-authenticate patient session
        patient = RegistrationModel.query.get(appointment.patient_id)
        if patient:
            login_user(patient, remember=True)

        flash(f"Payment failed: {failed_reason}. You can retry payment anytime from your dashboard.", "error")
        return redirect(url_for('dashboard.patient_appointments_page', uid=appointment.patient_id))

    flash(f"Payment failed: {failed_reason}.", "error")
    return redirect(url_for('home.home_page'))


# SSLCommerz Payment Cancel Callback
@dashboard.route('/payment/cancel', methods=['GET', 'POST'])
def sslcommerz_cancel():
    data = request.form.to_dict() if request.method == 'POST' else request.args.to_dict()
    current_app.logger.info(f"SSLCommerz Cancel Callback received: {data}")

    tran_id = data.get('tran_id')
    appointment_id_str = data.get('value_a')

    appointment = None
    if appointment_id_str:
        try:
            appointment = AppointmentModel.query.get(int(appointment_id_str))
        except (ValueError, TypeError):
            pass
    if not appointment and tran_id:
        appointment = AppointmentModel.query.filter_by(transaction_id=tran_id).first()

    if appointment:
        appointment.payment_status = 'unpaid'
        txn = PaymentTransactionModel.query.filter_by(tran_id=tran_id).first()
        if txn:
            txn.status = 'cancelled'
            import json
            txn.raw_response = json.dumps(data)
        db.session.commit()

        # Re-authenticate patient session
        patient = RegistrationModel.query.get(appointment.patient_id)
        if patient:
            login_user(patient, remember=True)

        flash("Payment was cancelled. You can choose to pay the consultation fee later.", "info")
        return redirect(url_for('dashboard.patient_appointments_page', uid=appointment.patient_id))

    flash("Payment transaction was cancelled.", "info")
    return redirect(url_for('home.home_page'))


# SSLCommerz Instant Payment Notification (IPN) Webhook
@dashboard.route('/payment/ipn', methods=['POST'])
def sslcommerz_ipn():
    data = request.form.to_dict()
    val_id = data.get('val_id')
    tran_id = data.get('tran_id')
    current_app.logger.info(f"SSLCommerz IPN received: val_id={val_id}, tran_id={tran_id}")

    if val_id and tran_id:
        validation_result = validate_sslcommerz_payment(val_id)
        if validation_result.get('status') in ['VALID', 'VALIDATED']:
            appointment = AppointmentModel.query.filter_by(transaction_id=tran_id).first()
            if appointment and appointment.payment_status != 'paid':
                amount_val = float(validation_result.get('amount', appointment.fee_amount or 0.0))
                appointment.payment_status = 'paid'
                appointment.payment_amount = amount_val
                appointment.payment_method = validation_result.get('card_type', 'SSLCommerz')
                appointment.bank_tran_id = validation_result.get('bank_tran_id', '')
                appointment.payment_date = datetime.now()
                db.session.commit()
                notify_payment_success(appointment, amount_val, tran_id)

    return jsonify({'status': 'IPN received'}), 200


















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
            fee_data = form.consultation_fee.data if form.consultation_fee.data is not None else 1000.0

            # image processing
            if sign:
                signature_image_name = secure_filename(sign.filename)
                timestamp = int(time.time())
                unique_filename = f"{timestamp}_{signature_image_name}"
                from app.core.storage_service import upload_file_to_storage
                upload_file_to_storage(sign, unique_filename)
                

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
                consultation_fee = fee_data,
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
            if form.consultation_fee.data is not None:
                get_info.consultation_fee = float(form.consultation_fee.data)

            sign = form.signature.data

            if sign and hasattr(sign, 'filename') and sign.filename:
                signature_image_name = secure_filename(sign.filename)
                timestamp = int(time.time())
                unique_filename = f"{timestamp}_{signature_image_name}"
                from app.core.storage_service import upload_file_to_storage
                upload_file_to_storage(sign, unique_filename)
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

    # If doctor/admin, filter by doc_id. If patient, filter by appointments, patient email, and patient names
    is_doctor_user = getattr(user, 'role', 'patient') == 'doctor' or user.is_admin
    if is_doctor_user:
        paged_history = PrescriptionModel.query.filter_by(doc_id=uid).order_by(PrescriptionModel.created_at.desc()).paginate(page=get_page, per_page=per_page, error_out=False)
        is_history = paged_history.items
    else:
        from sqlalchemy import or_
        from app.modules.dashboard.models import AppointmentModel

        # Query all appointment records belonging to this patient
        patient_appointments = AppointmentModel.query.filter(
            or_(
                AppointmentModel.patient_id == user.uid,
                AppointmentModel.patient_email == user.email
            )
        ).all()

        appt_ids = [a.id for a in patient_appointments]
        appt_names = [a.patient_name for a in patient_appointments if a.patient_name]

        # Name matching conditions
        name_conditions = [PrescriptionModel.patient_name.ilike(f"%{user.username}%")]
        if user.profile_info and getattr(user.profile_info, 'full_name', None):
            name_conditions.append(PrescriptionModel.patient_name.ilike(f"%{user.profile_info.full_name}%"))

        for name in set(appt_names):
            if name and name.strip():
                name_conditions.append(PrescriptionModel.patient_name.ilike(f"%{name.strip()}%"))

        query_conditions = []
        if appt_ids:
            query_conditions.append(PrescriptionModel.appointment_id.in_(appt_ids))
        query_conditions.extend(name_conditions)

        paged_history = PrescriptionModel.query.filter(
            or_(*query_conditions)
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





