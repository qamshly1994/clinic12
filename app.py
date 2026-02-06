import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

# ===== Database =====
db_url = os.environ.get("DATABASE_URL", "sqlite:///clinic.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ===== Models =====
class Doctor(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    specialty = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patients = db.relationship("Patient", backref="doctor", lazy=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"))

@login_manager.user_loader
def load_user(user_id):
    return Doctor.query.get(int(user_id))

# ===== Routes =====
@app.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        user = Doctor.query.filter_by(username=request.form["username"]).first()
        if not user or not bcrypt.check_password_hash(user.password_hash, request.form["password"]):
            flash("بيانات الدخول غير صحيحة")
            return redirect(url_for("login"))

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))

    if current_user.username == "admin":
        doctors = Doctor.query.filter(Doctor.username != "admin").all()
        return render_template("dashboard.html", doctor=current_user, doctors=doctors)

    return render_template("dashboard.html", doctor=current_user)

@app.route("/patients", methods=["GET", "POST"])
def patients():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))

    search_term = request.args.get('search')
    if search_term:
        patient_list = Patient.query.filter(
            Patient.doctor_id == current_user.id,
            (Patient.name.contains(search_term)) | (Patient.patient_id.contains(search_term))
        ).order_by(Patient.created_at.desc()).all()
    else:
        patient_list = Patient.query.filter_by(
            doctor_id=current_user.id
        ).order_by(Patient.created_at.desc()).all()

    if request.method == "POST":
        name = request.form["name"]
        notes = request.form["notes"]
        patient = Patient(name=name, notes=notes, doctor=current_user)
        db.session.add(patient)
        db.session.commit()
        flash(f"تم إضافة المريض بنجاح. رقم المريض: {patient.patient_id}")
        return redirect(url_for("patients"))

    return render_template("patients.html", patients=patient_list)

@app.route("/add_doctor", methods=["GET", "POST"])
def add_doctor():
    if not current_user.is_authenticated or current_user.username != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form["username"]
        full_name = request.form["full_name"]
        specialty = request.form["specialty"]
        password = request.form["password"]

        if Doctor.query.filter_by(username=username).first():
            flash("اسم المستخدم موجود بالفعل")
        else:
            hashed = bcrypt.generate_password_hash(password).decode("utf-8")
            doctor = Doctor(username=username, full_name=full_name, specialty=specialty, password_hash=hashed)
            db.session.add(doctor)
            db.session.commit()
            flash("تم إضافة الدكتور بنجاح")
            return redirect(url_for("dashboard"))

    doctors = Doctor.query.filter(Doctor.username != "admin").all()
    return render_template("add_doctor.html", doctors=doctors)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))

# ===== Initialize DB =====
with app.app_context():
    db.create_all()
    if not Doctor.query.filter_by(username="admin").first():
        password = bcrypt.generate_password_hash("admin123").decode("utf-8")
        admin = Doctor(username="admin", full_name="Admin", password_hash=password)
        db.session.add(admin)
        db.session.commit()

# ===== Run server =====
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
