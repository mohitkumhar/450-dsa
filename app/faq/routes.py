from flask import render_template
from app.faq import faq_bp

@faq_bp.route("/faq")
def faq():
    return render_template("faq.html")
