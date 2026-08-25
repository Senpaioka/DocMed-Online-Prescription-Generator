from flask import request, render_template, redirect, url_for, flash, Blueprint, Response, current_app
from app.extensions import db
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, current_user
from app.modules.pdf.models import PrescriptionModel
from app.modules.account.models import RegistrationModel
from app.modules.pdf.forms import PrescriptionForm
import uuid
import io
import os



# patient id generator
def short_uuid(length: int = 8) -> str:
    full_uuid = uuid.uuid4().hex 
    return full_uuid[:length] 


pdf_generator = Blueprint('pdf_generator', __name__, template_folder='templates')

import json

_medicine_cache = None

def get_medicine_data():
    global _medicine_cache
    if _medicine_cache is None:
        json_path = os.path.join(current_app.root_path, 'static', 'data', 'data.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                _medicine_cache = json.load(f)
        except Exception:
            _medicine_cache = []
    return _medicine_cache


from app.core.roles import doctor_required, role_required, UserRole


# Live Medicine Search (HTMX)
@pdf_generator.route('/search-medicines', methods=['GET', 'POST'])
@login_required
@doctor_required
def search_medicines():
    query = (request.args.get('search') or request.form.get('search') or '').strip().lower()
    matches = []
    if query and len(query) >= 2:
        all_meds = get_medicine_data()
        scored_matches = []
        
        for item in all_meds:
            name = str(item.get('name', '')).strip().lower()
            generic = str(item.get('generic', '')).strip().lower()
            brand = str(item.get('brand', '')).strip().lower()
            
            score = None
            
            # --- 1. MEDICINE NAME (Priority 1-4) ---
            if name == query:
                score = (0, len(name), name)
            elif name.startswith(query):
                score = (1, len(name), name)
            elif any(w.startswith(query) for w in name.split()):
                score = (2, len(name), name)
            elif query in name:
                score = (3, len(name), name)
                
            # --- 2. GENERIC NAME (Priority 5-8) ---
            elif generic == query:
                score = (4, len(generic), name)
            elif generic.startswith(query):
                score = (5, len(generic), name)
            elif any(w.startswith(query) for w in generic.split()):
                score = (6, len(generic), name)
            elif query in generic:
                score = (7, len(generic), name)
                
            # --- 3. BRAND / COMPANY (Priority 9) ---
            elif query in brand:
                score = (8, len(brand), name)
                
            if score is not None:
                scored_matches.append((score, item))
        
        # Sort by relevance priority, length of matched text, and name
        scored_matches.sort(key=lambda x: x[0])
        matches = [item for _, item in scored_matches[:5]]

    return render_template('pdf/_medicine_results.html', medicines=matches, query=query)


# Live Prescription Preview (HTMX)
@pdf_generator.route('/preview-live', methods=['POST'])
@login_required
@doctor_required
def preview_live():
    return render_template(
        'pdf/_prescription_live_preview.html',
        name=request.form.get('patient_name', ''),
        age=request.form.get('patient_age', ''),
        sex=request.form.get('patient_sex', ''),
        cc=request.form.get('cc', ''),
        bp=request.form.get('bp', ''),
        pulse=request.form.get('pulse', ''),
        temp=request.form.get('temp', ''),
        spo=request.form.get('spo', ''),
        inv=request.form.get('inv', ''),
        rx=request.form.get('rx', ''),
        advice=request.form.get('advice', '')
    )


@pdf_generator.route('/prescription', methods=['GET', 'POST'])
@login_required
@doctor_required
def document_page():
    # Require doctor to complete profile setup before generating prescriptions
    if not current_user.profile_info:
        flash("Please complete your doctor profile setup first before generating prescriptions.", "error")
        return redirect(url_for('dashboard.setup_page', uid=current_user.uid))

    form = PrescriptionForm()

    doctor_id = current_user.uid
    unique_id = short_uuid()

    appointment_id = request.args.get('appointment_id', type=int) or request.form.get('appointment_id', type=int)
    appointment = None
    if appointment_id:
        from app.modules.dashboard.models import AppointmentModel
        appointment = AppointmentModel.query.filter_by(id=appointment_id, doctor_id=current_user.uid).first()

    if request.method == 'GET':
        if appointment:
            form.patient_name.data = appointment.patient_name
            if appointment.reason:
                form.cc.data = appointment.reason
            if appointment.patient and appointment.patient.gender:
                gender = appointment.patient.gender.lower()
                if gender in ['male', 'female', 'other']:
                    form.patient_sex.data = gender
            
            # Auto-fill age from previous prescription if available
            past_rx = PrescriptionModel.query.filter_by(patient_name=appointment.patient_name).order_by(PrescriptionModel.created_at.desc()).first()
            if past_rx and past_rx.patient_age:
                form.patient_age.data = past_rx.patient_age

        if request.args.get('patient_name'):
            form.patient_name.data = request.args.get('patient_name')
        if request.args.get('patient_age', type=int):
            form.patient_age.data = request.args.get('patient_age', type=int)
        if request.args.get('patient_sex'):
            gender = request.args.get('patient_sex').lower()
            if gender in ['male', 'female', 'other']:
                form.patient_sex.data = gender
        if request.args.get('cc'):
            form.cc.data = request.args.get('cc')

    if request.method == 'POST':
        if form.validate_on_submit():
            name = form.patient_name.data
            age = form.patient_age.data
            sex = form.patient_sex.data

            cc = form.cc.data
            bp = form.bp.data
            pulse = form.pulse.data
            temp = form.temp.data
            spo = form.spo.data
            inv = form.inv.data

            rx = form.rx.data
            advice = form.advice.data

            # creating model object
            generate_prescription = PrescriptionModel(
                patient_id = unique_id,
                doc_id = doctor_id,
                patient_name = name,
                patient_age = age,
                patient_sex = sex,
                cc = cc,
                bp = bp,
                pulse = pulse,
                temp = temp,
                spo = spo,
                inv = inv,
                rx = rx,
                advice = advice,
                appointment_id = appointment.id if appointment else None
            )

            db.session.add(generate_prescription)

            # Automatically mark appointment as completed when prescription is generated
            if appointment:
                appointment.status = 'completed'
                db.session.add(appointment)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Something Went Wrong", "error")
                return redirect(url_for('pdf_generator.document_page')) 
            
            if appointment:
                # Dispatch real-time SSE & DB notification to patient
                try:
                    from app.core.notification_service import notify_patient_prescription_ready
                    notify_patient_prescription_ready(appointment=appointment, prescription_unique_id=unique_id)
                except Exception as ex:
                    current_app.logger.warning(f"Failed to push prescription notification: {ex}")

                flash(f"Prescription generated and appointment with {appointment.patient_name} marked as completed!", "success")
            
            return redirect(url_for('pdf_generator.pdf_prescription_preview', patient_id=unique_id))
        

    context = {
        'form': form,
        'appointment': appointment,
        'name': form.patient_name.data,
        'age': form.patient_age.data,
        'sex': form.patient_sex.data,
        'cc': form.cc.data,
        'bp': form.bp.data,
        'pulse': form.pulse.data,
        'temp': form.temp.data,
        'spo': form.spo.data,
        'inv': form.inv.data,
        'rx': form.rx.data,
        'advice': form.advice.data,
    }
    return render_template('pdf/prescription.html', **context)









@pdf_generator.route('/preview/<patient_id>')
@login_required
def pdf_prescription_preview(patient_id):
    get_patient = PrescriptionModel.query.filter_by(patient_id=patient_id).first_or_404()
    
    # Retrieve the prescribing doctor
    doctor = RegistrationModel.query.get(get_patient.doc_id) if get_patient.doc_id else None
    if not doctor:
        doctor = current_user

    context = {
        'patient': get_patient,
        'doctor': doctor,
    }

    return render_template('pdf/pdf_preview.html', **context)





from app.core.pdf_service import make_pdf_response


@pdf_generator.route('/generate_pdf/<uid>/<patient_id>')
def pdf_generator_page(uid, patient_id):
    """
    Renders / downloads the prescription PDF.
    - default: inline view
    - ?download=true or ?dl=1: force download attachment
    """
    get_patient = PrescriptionModel.query.filter_by(patient_id=patient_id).first_or_404()
    
    # Ensure we use the actual doctor associated with the prescription
    get_doctor = RegistrationModel.query.get(get_patient.doc_id) if get_patient.doc_id else None
    if not get_doctor:
        get_doctor = RegistrationModel.query.get_or_404(uid)

    download_mode = request.args.get('download', '').lower() in ('1', 'true', 'yes') or request.args.get('dl') == '1'

    clean_patient_name = "".join(c for c in (get_patient.patient_name or 'patient') if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"Rx_{clean_patient_name}_{get_patient.patient_id}.pdf"

    context = {
        'patient': get_patient,
        'doctor': get_doctor,
    }

    return make_pdf_response('pdf/pdf.html', context, filename=filename, download=download_mode)