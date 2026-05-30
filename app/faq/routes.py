from flask import render_template
from app.faq import faq_bp
from app.extensions import cache

@faq_bp.route("/faq")
@cache.cached(timeout=900)
def faq():
    return render_template("faq.html")

@faq_bp.route("/contact")
def contact():
    return render_template("placeholder.html", title="Contact Us")

@faq_bp.route("/privacy")
def privacy():
    return render_template("placeholder.html", title="Privacy Policy")

@faq_bp.route("/timeline")
def timeline():
    return render_template("placeholder.html", title="Timeline")

@faq_bp.route("/terms")
def terms():
    return render_template("placeholder.html", title="Terms of Service")

@faq_bp.route("/refund")
def refund():
    return render_template("placeholder.html", title="Refund Policy")

@faq_bp.route("/monthly-rewind")
def monthly_rewind():
    return render_template("placeholder.html", title="Monthly Rewind")
