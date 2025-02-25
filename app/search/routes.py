from flask import request, render_template, redirect, url_for, flash, Response, Blueprint
from app.app import db
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, current_user
from app.pdf.models import PrescriptionModel
from app.account.models import RegistrationModel
from app.pdf.forms import PrescriptionForm
from app.search.search import SearchForm
from sqlalchemy import or_


user_search = Blueprint('user_search', __name__, template_folder='templates')


@user_search.route('<int:uid>/results', methods=['POST'])
@login_required
def search_result_page(uid):
    form = SearchForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            get_search_data = form.search.data

            results = PrescriptionModel.query.filter(
                PrescriptionModel.doc_id == uid,  # Move this inside filter()
                or_(
                    PrescriptionModel.patient_id.ilike(f"%{get_search_data}%"),
                    PrescriptionModel.patient_name.ilike(f"%{get_search_data}%"),
                )
                ).all()


    context = {
        'search_result': results,
    }
    return render_template('search/search.html', **context)

