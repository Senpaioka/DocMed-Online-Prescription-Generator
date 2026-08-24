import logging
from flask import url_for
from app.extensions import db
from app.modules.dashboard.models import NotificationModel, AppointmentModel, ProfileSetupModel
from app.modules.account.models import RegistrationModel
from app.core.sse import sse_manager

logger = logging.getLogger(__name__)


def create_and_push_notification(
    user_id: int,
    title: str,
    message: str,
    event_type: str,
    appointment_id: int = None,
    link_url: str = None
) -> NotificationModel:
    """
    Persists a notification in DB and immediately pushes it through SSE to the active user session(s).
    """
    notification = NotificationModel(
        user_id=user_id,
        appointment_id=appointment_id,
        title=title,
        message=message,
        event_type=event_type,
        link_url=link_url,
        is_read=False
    )
    
    try:
        db.session.add(notification)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Notification] Failed to save notification to DB: {e}")
        # Proceed with in-memory payload push even if DB save hit an error
        notification.id = 0

    # Payload to push over SSE
    payload = notification.to_dict()
    # Also include the total unread count for real-time badge sync
    unread_count = NotificationModel.query.filter_by(user_id=user_id, is_read=False).count()
    payload['unread_count'] = unread_count

    # Real-time SSE dispatch
    sse_manager.publish_to_user(user_id=user_id, event_type=event_type, data=payload)
    logger.info(f"[Notification] Pushed '{event_type}' to user {user_id}: {title}")

    return notification


def notify_patient_appointment_confirmed(appointment: AppointmentModel):
    """Notify patient that doctor confirmed & scheduled the appointment."""
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doc_profile = ProfileSetupModel.query.filter_by(user_id=appointment.doctor_id).first()
    doctor_name = doc_profile.full_name if doc_profile and doc_profile.full_name else f"Dr. {doctor.username if doctor else 'Doctor'}"
    
    date_str = appointment.scheduled_date.strftime('%A, %d %B %Y') if appointment.scheduled_date else 'Soon'
    time_str = appointment.scheduled_time or ''
    schedule_text = f"{date_str} at {time_str}".strip()

    title = "Appointment Confirmed! 🗓️"
    message = f"{doctor_name} confirmed your appointment for {schedule_text}."
    if appointment.doctor_notes:
        message += f" Note: {appointment.doctor_notes}"

    link_url = url_for('dashboard.patient_appointments_page', uid=appointment.patient_id)
    
    return create_and_push_notification(
        user_id=appointment.patient_id,
        title=title,
        message=message,
        event_type="appointment_confirmed",
        appointment_id=appointment.id,
        link_url=link_url
    )


def notify_patient_appointment_rejected(appointment: AppointmentModel, reason: str = ""):
    """Notify patient that doctor declined the appointment request."""
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doc_profile = ProfileSetupModel.query.filter_by(user_id=appointment.doctor_id).first()
    doctor_name = doc_profile.full_name if doc_profile and doc_profile.full_name else f"Dr. {doctor.username if doctor else 'Doctor'}"

    title = "Appointment Request Declined ❌"
    message = f"{doctor_name} was unable to accept your appointment request."
    if reason:
        message += f" Reason: {reason}"

    link_url = url_for('dashboard.verified_doctors_page', uid=appointment.patient_id)

    return create_and_push_notification(
        user_id=appointment.patient_id,
        title=title,
        message=message,
        event_type="appointment_rejected",
        appointment_id=appointment.id,
        link_url=link_url
    )


def notify_patient_appointment_cancelled(appointment: AppointmentModel, reason: str = ""):
    """Notify patient that doctor cancelled a scheduled appointment."""
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doc_profile = ProfileSetupModel.query.filter_by(user_id=appointment.doctor_id).first()
    doctor_name = doc_profile.full_name if doc_profile and doc_profile.full_name else f"Dr. {doctor.username if doctor else 'Doctor'}"

    title = "Appointment Cancelled ⚠️"
    message = f"{doctor_name} cancelled your scheduled consultation."
    if reason:
        message += f" Reason: {reason}"

    link_url = url_for('dashboard.patient_appointments_page', uid=appointment.patient_id)

    return create_and_push_notification(
        user_id=appointment.patient_id,
        title=title,
        message=message,
        event_type="appointment_cancelled",
        appointment_id=appointment.id,
        link_url=link_url
    )


def notify_patient_prescription_ready(appointment: AppointmentModel, prescription_unique_id: str):
    """Notify patient that prescription has been generated and consultation completed."""
    doctor = RegistrationModel.query.get(appointment.doctor_id)
    doc_profile = ProfileSetupModel.query.filter_by(user_id=appointment.doctor_id).first()
    doctor_name = doc_profile.full_name if doc_profile and doc_profile.full_name else f"Dr. {doctor.username if doctor else 'Doctor'}"

    title = "Prescription Ready! 💊"
    message = f"{doctor_name} completed your consultation and generated your medical prescription."

    link_url = url_for('pdf_generator.pdf_prescription_preview', patient_id=prescription_unique_id)

    return create_and_push_notification(
        user_id=appointment.patient_id,
        title=title,
        message=message,
        event_type="appointment_completed",
        appointment_id=appointment.id,
        link_url=link_url
    )


def notify_doctor_new_appointment(appointment: AppointmentModel):
    """Notify doctor when a new appointment request is submitted by a patient."""
    title = "New Appointment Request 🩺"
    message = f"New appointment request from {appointment.patient_name} (Phone: {appointment.patient_phone})."

    link_url = url_for('dashboard.doctor_appointments_page', uid=appointment.doctor_id)

    return create_and_push_notification(
        user_id=appointment.doctor_id,
        title=title,
        message=message,
        event_type="new_appointment_request",
        appointment_id=appointment.id,
        link_url=link_url
    )
