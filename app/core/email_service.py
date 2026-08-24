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
