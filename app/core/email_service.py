import secrets
from datetime import datetime, timedelta
from flask import render_template, current_app
from flask_mailman import EmailMessage
from app.extensions import mail, db


def generate_otp(length=6) -> str:
    """Generate a secure numeric OTP of given length."""
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def send_email(subject, recipient, template_html, context, template_txt=None):
    """
    Generic helper to render and send HTML emails via flask-mailman.
    """
    html_body = render_template(template_html, **context)
    
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
    
    msg = EmailMessage(
        subject=subject,
        body=html_body,
        from_email=sender,
        to=[recipient]
    )
    msg.content_subtype = "html"
    
    try:
        msg.send()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {recipient}: {e}")
        return False


def send_verification_otp(user, expiry_minutes=10) -> bool:
    """
    Generate an OTP, persist it to the user model, and send the verification email.
    """
    otp = generate_otp(6)
    user.otp_code = otp
    user.otp_expiry = datetime.now() + timedelta(minutes=expiry_minutes)
    db.session.commit()

    context = {
        'user': user,
        'otp': otp,
        'expiry_minutes': expiry_minutes,
        'app_name': 'DocMed',
        'current_year': datetime.now().year
    }

    return send_email(
        subject='DocMed | Verify Your Email Address (OTP Code)',
        recipient=user.email,
        template_html='emails/otp_verification.html',
        context=context
    )


def send_welcome_email(user, dashboard_url=None) -> bool:
    """
    Send role-specific welcome email after successful email verification.
    """
    is_doctor = (getattr(user, 'role', '') == 'doctor') or getattr(user, 'is_doctor', False)
    
    if is_doctor:
        subject = 'Welcome to DocMed | Your Doctor Account is Active! 🩺'
        template_html = 'emails/welcome_doctor.html'
    else:
        subject = 'Welcome to DocMed | Your Account is Verified! 💙'
        template_html = 'emails/welcome_patient.html'

    context = {
        'user': user,
        'is_doctor': is_doctor,
        'dashboard_url': dashboard_url,
        'app_name': 'DocMed',
        'current_year': datetime.now().year
    }

    return send_email(
        subject=subject,
        recipient=user.email,
        template_html=template_html,
        context=context
    )


def send_password_reset_email(user, reset_url, expiry_minutes=30) -> bool:
    """
    Send secure password reset link to user.
    """
    context = {
        'user': user,
        'reset_url': reset_url,
        'expiry_minutes': expiry_minutes,
        'app_name': 'DocMed',
        'current_year': datetime.now().year
    }

    return send_email(
        subject='DocMed | Password Reset Request 🔒',
        recipient=user.email,
        template_html='emails/password_reset.html',
        context=context
    )


def send_doctor_approval_email(user, dashboard_url=None) -> bool:
    """
    Send congratulations email to doctor after being verified/approved by an admin.
    """
    context = {
        'user': user,
        'dashboard_url': dashboard_url,
        'app_name': 'DocMed',
        'current_year': datetime.now().year
    }

    return send_email(
        subject='Congratulations! Your Doctor Account is Approved 🩺🎉 | DocMed',
        recipient=user.email,
        template_html='emails/doctor_approved.html',
        context=context
    )


def send_appointment_confirmed_email(appointment, patient, doctor, doctor_profile=None, patient_dashboard_url=None) -> bool:
    """
    Send email to patient notifying them that their appointment has been confirmed & scheduled by the doctor.
    """
    doctor_display_name = doctor_profile.full_name if (doctor_profile and doctor_profile.full_name) else f"Dr. {doctor.username}"
    
    context = {
        'appointment': appointment,
        'patient': patient,
        'doctor': doctor,
        'doctor_profile': doctor_profile,
        'doctor_display_name': doctor_display_name,
        'patient_dashboard_url': patient_dashboard_url,
        'app_name': 'DocMed',
        'current_year': datetime.now().year
    }

    return send_email(
        subject=f'Appointment Confirmed with {doctor_display_name} 🗓️ | DocMed',
        recipient=appointment.patient_email or patient.email,
        template_html='emails/appointment_confirmed.html',
        context=context
    )


def send_appointment_cancelled_email(appointment, patient, doctor, doctor_profile=None, reason=None, patient_dashboard_url=None) -> bool:
    """
    Send email to patient notifying them that their appointment has been cancelled or rejected by the doctor.
    """
    doctor_display_name = doctor_profile.full_name if (doctor_profile and doctor_profile.full_name) else f"Dr. {doctor.username}"
    is_rejected = (appointment.status == 'rejected')

    subject = f'Appointment Update: {"Declined" if is_rejected else "Cancelled"} by {doctor_display_name} | DocMed'

    context = {
        'appointment': appointment,
        'patient': patient,
        'doctor': doctor,
        'doctor_profile': doctor_profile,
        'doctor_display_name': doctor_display_name,
        'reason': reason or appointment.doctor_notes,
        'is_rejected': is_rejected,
        'patient_dashboard_url': patient_dashboard_url,
        'app_name': 'DocMed',
        'current_year': datetime.now().year
    }

    return send_email(
        subject=subject,
        recipient=appointment.patient_email or patient.email,
        template_html='emails/appointment_cancelled.html',
        context=context
    )



