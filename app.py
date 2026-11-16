import os, uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, send_from_directory, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")

# Fix 1: Point SQLite to /tmp if DATABASE_URL isn't set
db_url = os.environ.get("DATABASE_URL", "sqlite:////tmp/school.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Fix 2: Point UPLOAD_FOLDER to /tmp so os.makedirs succeeds on Vercel
app.config["UPLOAD_FOLDER"] = "/tmp/uploads"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    class_name = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    resource_type = db.Column(db.String(60), default="Notes")
    subject = db.Column(db.String(100), default="")
    class_name = db.Column(db.String(80), default="")
    description = db.Column(db.Text, default="")
    filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subject = db.Column(db.String(100), default="")
    class_name = db.Column(db.String(80), default="")
    instructions = db.Column(db.Text, default="")
    due_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignment.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    answer = db.Column(db.Text, default="")
    filename = db.Column(db.String(255), default="")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("assignment_id", "student_id"),)

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subject = db.Column(db.String(100), default="")
    class_name = db.Column(db.String(80), default="")
    instructions = db.Column(db.Text, default="")
    questions = db.Column(db.Text, nullable=False)
    opens_at = db.Column(db.DateTime, nullable=False)
    closes_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ExamSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    answers = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("exam_id", "student_id"),)

class ExamAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=True)
    departed = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint("exam_id", "student_id"),)

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    assessment = db.Column(db.String(180), nullable=False)
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    feedback = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    details = db.Column(db.Text, default="")
    meeting_url = db.Column(db.String(500), default="")
    starts_at = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    event = db.Column(db.String(180))
    detail = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    body = db.Column(db.String(500), default="")
    target_url = db.Column(db.String(300), default="/dashboard")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ResourceAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    accessed_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

class ChatSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    topic = db.Column(db.String(180), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="requested")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ExamEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    event = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def notify_user(user_id, title, body, target="/dashboard"):
    db.session.add(Notification(user_id=user_id, title=title, body=body, target_url=target))

def notify_students(title, body, target):
    for student in User.query.filter_by(role="student").all():
        notify_user(student.id, title, body, target)

def current_user():
    return db.session.get(User, session.get("user_id")) if session.get("user_id") else None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user().role not in allowed:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return deco

def log(event, detail=""):
    u = current_user()
    if u:
        db.session.add(Activity(user_id=u.id, event=event, detail=detail[:300]))
        db.session.commit()

def parse_dt(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M") if value else None

@app.context_processor
def inject():
    u = current_user()
    unread = Notification.query.filter_by(user_id=u.id, is_read=False).count() if u else 0
    return {"me": u, "now": datetime.utcnow(), "unread_notifications": unread,
            "db_student_name": lambda uid: (db.session.get(User, uid).name if db.session.get(User, uid) else "Unknown student")}

@app.route("/")
def index():
    if current_user(): return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/academic-office")
def academic_office_portal():
    if current_user():
        if current_user().role == "admin":
            return redirect(url_for("dashboard"))
        return redirect(url_for("dashboard"))
    return render_template("academic_office_portal.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email = request.form["name"].strip(), request.form["email"].strip().lower()
        password, role = request.form["password"], request.form.get("role","student")
        if role not in ("student","teacher"): role = "student"
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
        else:
            u = User(name=name, email=email, password=generate_password_hash(password),
                     role=role, class_name=request.form.get("class_name","").strip())
            db.session.add(u); db.session.commit()
            session["user_id"] = u.id
            db.session.add(StudySession(user_id=u.id))
            db.session.commit()
            flash("Your account has been created.", "success")
            return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if u and check_password_hash(u.password, request.form["password"]):
            session.clear(); session["user_id"] = u.id
            db.session.add(StudySession(user_id=u.id))
            db.session.commit()
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    u = current_user()
    if u:
        active = StudySession.query.filter_by(user_id=u.id, ended_at=None).order_by(StudySession.started_at.desc()).first()
        if active:
            active.ended_at = datetime.utcnow()
            active.last_seen = datetime.utcnow()
            db.session.commit()
    session.clear(); return redirect(url_for("index"))

@app.route("/activity/ping", methods=["POST"])
@login_required
def activity_ping():
    u = current_user()
    active = StudySession.query.filter_by(user_id=u.id, ended_at=None).order_by(StudySession.started_at.desc()).first()
    if not active:
        active = StudySession(user_id=u.id); db.session.add(active)
    active.last_seen = datetime.utcnow()
    db.session.commit()
    return jsonify(ok=True)

@app.route("/activity/leave", methods=["POST"])
@login_required
def activity_leave():
    u = current_user()
    active = StudySession.query.filter_by(user_id=u.id, ended_at=None).order_by(StudySession.started_at.desc()).first()
    if active:
        active.last_seen = datetime.utcnow()
        active.ended_at = datetime.utcnow()
        db.session.commit()
    return jsonify(ok=True)

@app.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user().id).order_by(Notification.created_at.desc()).all()
    for n in items: n.is_read = True
    db.session.commit()
    return render_template("notifications.html", items=items)

@app.route("/chat-schedule", methods=["GET","POST"])
@login_required
def chat_schedule():
    if request.method == "POST":
        recipient = db.session.get(User, int(request.form["recipient"]))
        starts = parse_dt(request.form.get("starts_at"))
        topic = request.form.get("topic","").strip()
        if recipient and recipient.id != current_user().id and starts and topic:
            item = ChatSchedule(requester_id=current_user().id, recipient_id=recipient.id, topic=topic, starts_at=starts)
            db.session.add(item)
            notify_user(recipient.id, "Private chat requested", f"{current_user().name} requested a chat: {topic}", "/chat-schedule")
            db.session.commit()
            flash("Your private chat request has been sent.", "success")
        else: flash("Please complete all chat request details.", "error")
        return redirect(url_for("chat_schedule"))
    mine = ChatSchedule.query.filter((ChatSchedule.requester_id==current_user().id)|(ChatSchedule.recipient_id==current_user().id)).order_by(ChatSchedule.starts_at.asc()).all()
    people = User.query.filter(User.id != current_user().id).order_by(User.name).all()
    return render_template("chat_schedule.html", items=mine, people=people)

@app.route("/chat-schedule/<int:sid>/status", methods=["POST"])
@login_required
def chat_schedule_status(sid):
    item = db.session.get(ChatSchedule, sid)
    if item and current_user().id == item.recipient_id and request.form.get("status") in ("accepted","declined"):
        item.status = request.form["status"]
        notify_user(item.requester_id, "Chat request updated", f"Your chat request was {item.status}.", "/chat-schedule")
        db.session.commit()
    return redirect(url_for("chat_schedule"))

@app.route("/monitoring")
@roles("teacher","admin")
def monitoring():
    students = User.query.filter_by(role="student").order_by(User.name).all()
    rows = []
    for student in students:
        sessions = StudySession.query.filter_by(user_id=student.id).order_by(StudySession.started_at.desc()).all()
        seconds = sum(max(0, int(((x.ended_at or x.last_seen)-x.started_at).total_seconds())) for x in sessions)
        recent_rows = ResourceAccess.query.filter_by(user_id=student.id).order_by(ResourceAccess.accessed_at.desc()).limit(5).all()
        recent = [{"title": (db.session.get(Resource, access.resource_id).title if db.session.get(Resource, access.resource_id) else "Removed resource"),
                   "accessed_at": access.accessed_at} for access in recent_rows]
        rows.append({"student":student,"sessions":sessions[:5],"minutes":seconds//60,"recent":recent})
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(100).all()
    exam_events = ExamEvent.query.order_by(ExamEvent.created_at.desc()).limit(100).all()
    return render_template("monitoring.html", rows=rows, activities=activities, exam_events=exam_events)

@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    log("Opened dashboard")
    return render_template("dashboard.html",
        resources=Resource.query.order_by(Resource.created_at.desc()).limit(5).all(),
        assignments=Assignment.query.order_by(Assignment.due_at.asc()).all(),
        exams=Exam.query.order_by(Exam.opens_at.asc()).all(),
        meetings=Meeting.query.order_by(Meeting.starts_at.asc()).limit(5).all(),
        announcements=Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all(),
        users=User.query.count(), activity=Activity.query.order_by(Activity.created_at.desc()).limit(12).all(),
        student_count=User.query.filter_by(role="student").count(),
        teacher_count=User.query.filter_by(role="teacher").count(),
        admin_count=User.query.filter_by(role="admin").count(),
        staff_directory=User.query.filter(User.role.in_(["teacher","admin"])).order_by(User.role, User.name).limit(12).all())

@app.route("/resources", methods=["GET","POST"])
@login_required
def resources():
    if request.method == "POST":
        if current_user().role not in ("teacher","admin"): abort_403()
        f = request.files.get("file")
        if f and f.filename:
            filename = str(uuid.uuid4()) + "_" + secure_filename(f.filename)
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            r = Resource(title=request.form["title"], resource_type=request.form.get("resource_type","Notes"),
                subject=request.form.get("subject",""), class_name=request.form.get("class_name",""),
                description=request.form.get("description",""),
                filename=filename, uploaded_by=current_user().id)
            db.session.add(r); db.session.flush()
            notify_students("New learning resource", f"{r.title} has been uploaded.", "/resources")
            db.session.commit(); log("Uploaded resource", r.title)
            flash("Learning material uploaded.", "success")
        return redirect(url_for("resources"))
    items = Resource.query.order_by(Resource.created_at.desc()).all()
    return render_template("resources.html", items=items)

@app.route("/uploads/<filename>")
@login_required
def download(filename):
    item = Resource.query.filter_by(filename=filename).first()
    if not item: return "File not found", 404
    db.session.add(ResourceAccess(user_id=current_user().id, resource_id=item.id))
    db.session.commit()
    log("Accessed resource", item.title)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

@app.route("/assignments", methods=["GET","POST"])
@login_required
def assignments():
    if request.method == "POST":
        if current_user().role not in ("teacher","admin"): abort_403()
        a = Assignment(title=request.form["title"], subject=request.form.get("subject",""),
            class_name=request.form.get("class_name",""), instructions=request.form.get("instructions",""),
            due_at=parse_dt(request.form.get("due_at")), created_by=current_user().id)
        db.session.add(a); db.session.flush()
        notify_students("New assignment", f"{a.title} has been published.", "/assignments")
        db.session.commit(); flash("Assignment published.", "success")
        return redirect(url_for("assignments"))
    items = Assignment.query.order_by(Assignment.due_at.asc()).all()
    submissions = {s.assignment_id:s for s in Submission.query.filter_by(student_id=current_user().id).all()}
    return render_template("assignments.html", items=items, submissions=submissions)

@app.route("/assignments/<int:aid>/submit", methods=["POST"])
@roles("student")
def submit_assignment(aid):
    a = db.session.get(Assignment, aid)
    if not a: return "Not found", 404
    old = Submission.query.filter_by(assignment_id=aid, student_id=current_user().id).first()
    f = request.files.get("file"); filename = ""
    if f and f.filename:
        filename = str(uuid.uuid4()) + "_" + secure_filename(f.filename)
        f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    if old:
        old.answer = request.form.get("answer",""); old.filename = filename or old.filename
        old.submitted_at = datetime.utcnow()
    else:
        db.session.add(Submission(assignment_id=aid, student_id=current_user().id,
            answer=request.form.get("answer",""), filename=filename))
    db.session.commit(); log("Submitted assignment", a.title)
    flash("Your work has been submitted.", "success")
    return redirect(url_for("assignments"))

@app.route("/exams", methods=["GET","POST"])
@login_required
def exams():
    if request.method == "POST":
        if current_user().role not in ("teacher","admin"): abort_403()
        opens, closes = parse_dt(request.form["opens_at"]), parse_dt(request.form["closes_at"])
        if not opens or not closes or closes <= opens:
            flash("Choose a valid examination window.", "error")
        else:
            e = Exam(title=request.form["title"], subject=request.form.get("subject",""),
                class_name=request.form.get("class_name",""), instructions=request.form.get("instructions",""),
                questions=request.form["questions"], opens_at=opens, closes_at=closes,
                duration_minutes=max(1, int(request.form.get("duration_minutes",60))), created_by=current_user().id)
            db.session.add(e); db.session.flush()
            notify_students("Examination scheduled", f"{e.title} is scheduled.", "/exams")
            db.session.commit(); flash("Examination scheduled.", "success")
        return redirect(url_for("exams"))
    items = Exam.query.order_by(Exam.opens_at.asc()).all()
    done = {s.exam_id for s in ExamSubmission.query.filter_by(student_id=current_user().id).all()}
    return render_template("exams.html", items=items, done=done)

@app.route("/exams/<int:eid>", methods=["GET","POST"])
@roles("student")
def take_exam(eid):
    e = db.session.get(Exam, eid)
    if not e: return "Not found", 404
    existing_submission = ExamSubmission.query.filter_by(exam_id=eid, student_id=current_user().id).first()
    if existing_submission:
        flash("You have already submitted this examination.", "error")
        return redirect(url_for("exams"))

    now = datetime.utcnow()
    if now < e.opens_at or now > e.closes_at:
        flash("This examination is not currently open.", "error")
        return redirect(url_for("exams"))

    attempt = ExamAttempt.query.filter_by(exam_id=eid, student_id=current_user().id).first()
    if attempt and attempt.submitted_at:
        flash("This examination attempt has already been closed.", "error")
        return redirect(url_for("exams"))
    if not attempt:
        deadline = min(e.closes_at, now + timedelta(minutes=e.duration_minutes))
        attempt = ExamAttempt(exam_id=e.id, student_id=current_user().id, deadline=deadline)
        db.session.add(attempt)
        db.session.commit()

    qs = [q.strip() for q in e.questions.splitlines() if q.strip()]
    if request.method == "POST":
        if now > attempt.deadline:
            # The attempt is still recorded, but the timer cannot be restarted.
            flash("The examination time has ended. Your submitted answers were recorded.", "error")
        answers = "\\n".join(f"{q}: {request.form.get('answer_'+str(i),'')}" for i,q in enumerate(qs))
        db.session.add(ExamSubmission(exam_id=e.id, student_id=current_user().id, answers=answers))
        attempt.submitted_at = now
        attempt.departed = request.form.get("departure_detected") == "1"
        if attempt.departed:
            db.session.add(ExamEvent(exam_id=e.id, student_id=current_user().id, event="page_hidden_auto_submit"))
        notify_user(current_user().id, "Examination submitted", f"Your submission for {e.title} was recorded.", "/exams")
        db.session.commit()
        log("Submitted examination", e.title + (" (page departure detected)" if attempt.departed else ""))
        flash("Examination submitted.", "success")
        return redirect(url_for("exams"))
    return render_template("take_exam.html", exam=e, questions=qs, deadline=attempt.deadline)


@app.route("/exams/<int:eid>/depart", methods=["POST"])
@roles("student")
def exam_depart(eid):
    e = db.session.get(Exam, eid)
    attempt = ExamAttempt.query.filter_by(exam_id=eid, student_id=current_user().id).first()
    if not e or not attempt or attempt.submitted_at:
        return jsonify(ok=False), 409
    if ExamSubmission.query.filter_by(exam_id=eid, student_id=current_user().id).first():
        return jsonify(ok=False), 409
    qs = [q.strip() for q in e.questions.splitlines() if q.strip()]
    answers = "\\n".join(f"{q}: {request.form.get('answer_'+str(i),'')}" for i,q in enumerate(qs))
    db.session.add(ExamSubmission(exam_id=e.id, student_id=current_user().id, answers=answers))
    attempt.submitted_at = datetime.utcnow()
    attempt.departed = True
    db.session.add(ExamEvent(exam_id=e.id, student_id=current_user().id, event="page_hidden_auto_submit"))
    notify_user(current_user().id, "Examination submitted", f"Your submission for {e.title} was recorded after leaving the exam page.", "/exams")
    db.session.commit()
    log("Submitted examination", e.title + " (page departure detected)")
    return jsonify(ok=True)

@app.route("/messages", methods=["GET","POST"])
@login_required
def messages():
    if request.method == "POST":
        recipient = db.session.get(User, int(request.form["recipient"]))
        if recipient and recipient.id != current_user().id and request.form.get("body","").strip():
            db.session.add(Message(sender_id=current_user().id, recipient_id=recipient.id, body=request.form["body"].strip()))
            notify_user(recipient.id, "New message", f"New message from {current_user().name}.", "/messages")
            db.session.commit(); flash("Message sent.", "success")
        return redirect(url_for("messages"))
    msgs = Message.query.filter((Message.sender_id==current_user().id)|(Message.recipient_id==current_user().id)).order_by(Message.created_at.desc()).all()
    people = User.query.filter(User.id != current_user().id).order_by(User.name).all()
    return render_template("messages.html", msgs=msgs, people=people)

@app.route("/meetings", methods=["GET","POST"])
@login_required
def meetings():
    if request.method == "POST":
        if current_user().role not in ("teacher","admin"): abort_403()
        m = Meeting(title=request.form["title"], details=request.form.get("details",""),
            meeting_url=request.form.get("meeting_url",""), starts_at=parse_dt(request.form["starts_at"]),
            created_by=current_user().id)
        db.session.add(m); db.session.flush()
        notify_students("New academic meeting", f"{m.title} has been scheduled.", "/meetings")
        db.session.commit(); flash("Meeting scheduled.", "success")
        return redirect(url_for("meetings"))
    return render_template("meetings.html", items=Meeting.query.order_by(Meeting.starts_at.asc()).all())

@app.route("/announcements", methods=["GET","POST"])
@login_required
def announcements():
    if request.method == "POST":
        if current_user().role not in ("teacher","admin"): abort_403()
        a = Announcement(title=request.form["title"], body=request.form["body"], created_by=current_user().id)
        db.session.add(a); db.session.flush()
        notify_students("School announcement", a.title, "/announcements")
        db.session.commit(); flash("Announcement published.", "success")
        return redirect(url_for("announcements"))
    return render_template("announcements.html", items=Announcement.query.order_by(Announcement.created_at.desc()).all())

@app.route("/results", methods=["GET","POST"])
@login_required
def results():
    if request.method == "POST":
        if current_user().role not in ("teacher", "admin"): abort_403()
        student = db.session.get(User, int(request.form.get("student_id", 0)))
        try:
            score = float(request.form.get("score", ""))
            maximum = float(request.form.get("max_score", ""))
        except ValueError:
            score, maximum = -1, 0
        subject = request.form.get("subject", "").strip()
        assessment = request.form.get("assessment", "").strip()
        if not student or student.role != "student" or not subject or not assessment or maximum <= 0 or score < 0 or score > maximum:
            flash("Enter a valid student, subject, assessment and score.", "error")
        else:
            db.session.add(Grade(student_id=student.id, teacher_id=current_user().id,
                subject=subject, assessment=assessment, score=score, max_score=maximum,
                feedback=request.form.get("feedback", "").strip()))
            notify_user(student.id, "New academic result", f"A result for {subject} has been recorded.", "/results")
            db.session.commit()
            flash("Academic result recorded.", "success")
        return redirect(url_for("results"))
    if current_user().role in ("teacher", "admin"):
        items = Grade.query.order_by(Grade.created_at.desc()).all()
        students = User.query.filter_by(role="student").order_by(User.name).all()
    else:
        items = Grade.query.filter_by(student_id=current_user().id).order_by(Grade.created_at.desc()).all()
        students = []
    return render_template("results.html", items=items, students=students)

@app.route("/admin/users")
@roles("admin")
def admin_users():
    return render_template("users.html", users=User.query.order_by(User.created_at.desc()).all())

@app.route("/admin/promote/<int:uid>", methods=["POST"])
@roles("admin")
def promote(uid):
    u = db.session.get(User, uid)
    if u and u.id != current_user().id and request.form["role"] in ("student","teacher","admin"):
        u.role = request.form["role"]; db.session.commit()
    return redirect(url_for("admin_users"))

@app.errorhandler(403)
def forbidden(e): return render_template("403.html"), 403

def abort_403():
    from flask import abort
    abort(403)

def init_db():
    with app.app_context():
        db.create_all()
        # Lightweight SQLite upgrade for users replacing an earlier starter version.
        if db.engine.dialect.name == "sqlite":
            columns = {column["name"] for column in inspect(db.engine).get_columns("resource")}
            if "resource_type" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE resource ADD COLUMN resource_type VARCHAR(60) DEFAULT 'Notes'"))
        if not User.query.filter_by(email="admin@school.local").first():
            db.session.add(User(name="System Administrator", email="admin@school.local",
                password=generate_password_hash("ChangeMe123!"), role="admin"))
            db.session.commit()

init_db()

if __name__ == "__main__":
    app.run(debug=True)
