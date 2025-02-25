from flask import request, render_template, redirect, url_for, flash, Response, Blueprint, current_app
from app.app import db
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, current_user
from app.pdf.models import PrescriptionModel
from app.account.models import RegistrationModel
from app.pdf.forms import PrescriptionForm
import uuid



# patient id generator
def short_uuid(length: int = 8) -> str:
    full_uuid = uuid.uuid4().hex 
    return full_uuid[:length] 


pdf_generator = Blueprint('pdf_generator', __name__, template_folder='templates')



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







@pdf_generator.route('/generate_pdf/<uid>/<patient_id>')
def pdf_generator_page(uid, patient_id):

    pass

    # # getting patient prescription
    # get_patient = PrescriptionModel.query.filter_by(patient_id=patient_id).first()

    # # getting doctor info
    # get_doctor = RegistrationModel.query.get(uid)

    # context = {
    #     'patient': get_patient,
    #     'doctor': get_doctor,
    # }

    # html_content = render_template('pdf/pdf.html', **context)

    # print(html_content)
    # pdf = HTML(string=html_content, base_url=request.host_url).write_pdf()


    # # Return PDF as a response
    # return Response(pdf, mimetype='application/pdf', headers={
    #     "Content-Disposition": "inline; filename=prescription.pdf"
    # })






    