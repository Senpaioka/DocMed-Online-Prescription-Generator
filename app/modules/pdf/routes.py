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
        for item in all_meds:
            name = str(item.get('name', '')).lower()
            generic = str(item.get('generic', '')).lower()
            brand = str(item.get('brand', '')).lower()
            if query in name or query in generic or query in brand:
                matches.append(item)
                if len(matches) >= 15:
                    break

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
                advice = advice
            )

            db.session.add(generate_prescription)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Something Went Wrong", "error")
                return redirect(url_for('pdf_generator.document_page')) 
            
            return redirect(url_for('pdf_generator.pdf_prescription_preview', patient_id=unique_id))
        

    context = {
        'form': form,
    }
    return render_template('pdf/prescription.html', **context)









@pdf_generator.route('/preview/<patient_id>')
@login_required
def pdf_prescription_preview(patient_id):
    
    get_patient = PrescriptionModel.query.filter_by(patient_id=patient_id).first()

    context = {
        'patient': get_patient,
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
    get_doctor = RegistrationModel.query.get_or_404(uid)

    download_mode = request.args.get('download', '').lower() in ('1', 'true', 'yes') or request.args.get('dl') == '1'

    clean_patient_name = "".join(c for c in (get_patient.patient_name or 'patient') if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"Rx_{clean_patient_name}_{get_patient.patient_id}.pdf"

    context = {
        'patient': get_patient,
        'doctor': get_doctor,
    }

    return make_pdf_response('pdf/pdf.html', context, filename=filename, download=download_mode)