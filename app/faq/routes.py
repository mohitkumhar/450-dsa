from flask import render_template
from app.faq import faq_bp
from app.extensions import cache

@faq_bp.route("/faq")
@cache.cached(timeout=900)
def faq():
    return render_template("faq.html")
