from flask import render_template, Blueprint


home = Blueprint('home', __name__, template_folder='templates')


@home.route('/')
def home_page():
    return render_template('home/home.html')