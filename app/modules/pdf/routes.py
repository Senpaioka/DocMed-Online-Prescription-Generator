from flask import request, render_template, redirect, url_for, flash, Blueprint, Response, current_app
from app.extensions import db
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, current_user
from app.modules.pdf.models import PrescriptionModel
from app.modules.account.models import RegistrationModel
from app.modules.pdf.forms import PrescriptionForm
import uuid
from xhtml2pdf import pisa
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


# Live Medicine Search (HTMX)
@pdf_generator.route('/search-medicines', methods=['GET', 'POST'])
@login_required
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
def document_page():

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





# Function to convert HTML to PDF and return it as response
from flask import render_template, make_response, current_app
from xhtml2pdf import pisa
import io
import os

def create_pdf(template_name, context):
    html = render_template(template_name, **context)
    pdf = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        html, dest=pdf, link_callback=lambda uri, rel: os.path.join(current_app.root_path, uri.lstrip('/'))
    )

    if pisa_status.err:
        return "Error generating PDF", 500

    pdf.seek(0)
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=prescription.pdf'
    return response



@pdf_generator.route('/generate_pdf/<uid>/<patient_id>')
def pdf_generator_page(uid, patient_id):

    # getting patient prescription
    get_patient = PrescriptionModel.query.filter_by(patient_id=patient_id).first()

    # getting doctor info
    get_doctor = RegistrationModel.query.get(uid)

    context = {
        'patient': get_patient,
        'doctor': get_doctor,
    }
    # return render_template('pdf/pdf.html', **context)

    return create_pdf('pdf/pdf.html', context)
    




















    