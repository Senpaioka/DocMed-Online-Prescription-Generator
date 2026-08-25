import uuid
import time
import requests
import json
from flask import current_app, url_for
from app.extensions import db
from app.modules.dashboard.models import PaymentTransactionModel


def initiate_sslcommerz_payment(appointment, amount, patient, doctor):
    """
    Initiate a transaction session with SSLCommerz V4 API.
    Returns dict with status ('SUCCESS' or 'FAILED') and GatewayPageURL or error message.
    """
    store_id = current_app.config.get('SSLCOMMERZ_STORE_ID', 'perso6a8d2b801d53a')
    store_passwd = current_app.config.get('SSLCOMMERZ_STORE_PASSWORD', 'perso6a8d2b801d53a@ssl')
    api_url = current_app.config.get('SSLCOMMERZ_API_URL', 'https://sandbox.sslcommerz.com/gwprocess/v4/api.php')

    formatted_amount = f"{float(amount):.2f}"
    tran_id = f"TXN_{appointment.id}_{int(time.time())}_{uuid.uuid4().hex[:6].upper()}"

    # Build callback URLs
    success_url = url_for('dashboard.sslcommerz_success', _external=True)
    fail_url = url_for('dashboard.sslcommerz_fail', _external=True)
    cancel_url = url_for('dashboard.sslcommerz_cancel', _external=True)
    ipn_url = url_for('dashboard.sslcommerz_ipn', _external=True)

    patient_name = appointment.patient_name or patient.username or "Patient"
    patient_email = appointment.patient_email or patient.email or "patient@docmed.com"
    patient_phone = appointment.patient_phone or "01700000000"

    post_data = {
        'store_id': store_id,
        'store_passwd': store_passwd,
        'total_amount': formatted_amount,
        'currency': 'BDT',
        'tran_id': tran_id,
        'success_url': success_url,
        'fail_url': fail_url,
        'cancel_url': cancel_url,
        'ipn_url': ipn_url,
        
        # Customer Info
        'cus_name': patient_name,
        'cus_email': patient_email,
        'cus_add1': 'Dhaka, Bangladesh',
        'cus_city': 'Dhaka',
        'cus_country': 'Bangladesh',
        'cus_phone': patient_phone,
        
        # Product Info
        'shipping_method': 'NO',
        'product_name': f'Doctor Consultation - Appointment #{appointment.id}',
        'product_category': 'Medical Consultation',
        'product_profile': 'general',
        
        # Custom Parameters
        'value_a': str(appointment.id),
        'value_b': str(patient.uid),
        'value_c': str(doctor.uid),
        'value_d': formatted_amount,
    }

    try:
        current_app.logger.info(f"Initiating SSLCommerz payment for Appt #{appointment.id}, Amount={formatted_amount}, TranID={tran_id}")
        response = requests.post(api_url, data=post_data, timeout=30)
        
        try:
            resp_json = response.json()
        except Exception:
            current_app.logger.error(f"SSLCommerz invalid non-JSON response: {response.text}")
            return {
                'status': 'FAILED',
                'message': 'Failed to parse response from SSLCommerz payment gateway.'
            }

        status = resp_json.get('status')
        if status == 'SUCCESS' and resp_json.get('GatewayPageURL'):
            # Record initiated payment transaction in DB
            txn = PaymentTransactionModel(
                appointment_id=appointment.id,
                patient_id=patient.uid,
                doctor_id=doctor.uid,
                tran_id=tran_id,
                amount=float(formatted_amount),
                currency='BDT',
                status='initiated',
                raw_response=json.dumps(resp_json)
            )
            appointment.transaction_id = tran_id
            appointment.payment_status = 'pending'
            db.session.add(txn)
            db.session.commit()

            return {
                'status': 'SUCCESS',
                'gateway_url': resp_json.get('GatewayPageURL'),
                'sessionkey': resp_json.get('sessionkey'),
                'tran_id': tran_id
            }
        else:
            failed_reason = resp_json.get('failedreason', 'Unknown error from SSLCommerz.')
            current_app.logger.error(f"SSLCommerz session creation failed: {failed_reason}")
            return {
                'status': 'FAILED',
                'message': failed_reason
            }

    except requests.RequestException as req_err:
        current_app.logger.error(f"SSLCommerz API request exception: {req_err}")
        return {
            'status': 'FAILED',
            'message': f'Network error connecting to payment gateway: {req_err}'
        }


def validate_sslcommerz_payment(val_id):
    """
    Validate a transaction using the SSLCommerz validation API server.
    """
    if not val_id:
        return {'status': 'INVALID', 'message': 'Missing validation ID (val_id)'}

    store_id = current_app.config.get('SSLCOMMERZ_STORE_ID', 'perso6a8d2b801d53a')
    store_passwd = current_app.config.get('SSLCOMMERZ_STORE_PASSWORD', 'perso6a8d2b801d53a@ssl')
    validation_url = current_app.config.get(
        'SSLCOMMERZ_VALIDATION_URL',
        'https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php'
    )

    params = {
        'val_id': val_id,
        'store_id': store_id,
        'store_passwd': store_passwd,
        'format': 'json'
    }

    try:
        response = requests.get(validation_url, params=params, timeout=30)
        resp_json = response.json()
        return resp_json
    except Exception as e:
        current_app.logger.error(f"Error validating SSLCommerz payment with val_id {val_id}: {e}")
        return {'status': 'ERROR', 'message': str(e)}
