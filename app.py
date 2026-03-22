from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "change_this_to_a_secure_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///learning_app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Platform-level payment details
PLATFORM_UPI = "kambojuudaykiran55@okaxis"

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(30), nullable=False)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Completion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_new = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LecturerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bio = db.Column(db.Text, default="")
    experience_years = db.Column(db.Integer, default=0)
    subjects = db.Column(db.String(255), default="")
    payment_upi = db.Column(db.String(128), default="")

class SavedLecturer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    syllabus = db.Column(db.Text, nullable=False)
    duration_min = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

    # Schema upgrade: add payment_upi to lecturer_profile when missing
    conn = db.engine.connect()
    try:
        result = conn.execute(text("PRAGMA table_info('lecturer_profile')")).mappings().all()
        columns = [row['name'] for row in result]
        if 'payment_upi' not in columns:
            conn.execute(text("ALTER TABLE lecturer_profile ADD COLUMN payment_upi VARCHAR(128) DEFAULT ''"))
    finally:
        conn.close()

    if not User.query.filter_by(username="student1").first():
        db.session.add(User(username="student1", password="studentpass", role="student"))
    if not User.query.filter_by(username="lecturer1").first():
        db.session.add(User(username="lecturer1", password="lecturerpass", role="lecturer"))

    if Lesson.query.count() == 0:
        db.session.add_all([
            Lesson(title="Intro to Python", content="Variables, loops, functions"),
            Lesson(title="Web with Flask", content="Routes, templates, sessions"),
        ])

    if Notification.query.count() == 0:
        student = User.query.filter_by(username="student1").first()
        db.session.add_all([
            Notification(user_id=student.id, text="New video released by followed lecturer: 'Advanced Flask Patterns'", is_new=True),
            Notification(user_id=student.id, text="Your question in Queries got a reply: 'Use SQLAlchemy for ORM.'", is_new=True),
            Notification(user_id=student.id, text="Weekly report is ready.", is_new=False),
            Notification(user_id=student.id, text="New app update: UI improved with sidebar notifications.", is_new=True),
        ])

    if LecturerProfile.query.count() == 0:
        lecturer = User.query.filter_by(username="lecturer1").first()
        db.session.add(LecturerProfile(
            user_id=lecturer.id,
            bio="Experienced Python instructor focused on practical coding and web development.",
            experience_years=10,
            subjects="Python, Flask, WebDev",
            payment_upi="lecturer@okaxis"
        ))

    if Video.query.count() == 0:
        lecturer = User.query.filter_by(username="lecturer1").first()
        db.session.add_all([
            Video(lecturer_id=lecturer.id, title="Advanced Flask Patterns", syllabus="1. Blueprints\n2. Middleware\n3. Testing\n", duration_min=15, price=5.0),
            Video(lecturer_id=lecturer.id, title="Python Data Structures", syllabus="1. Lists\n2. Dicts\n3. Sets\n", duration_min=12, price=4.0),
        ])

    db.session.commit()

def get_student_notifications(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return []

    user_notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    notifs = [{"id": n.id, "text": n.text, "is_new": n.is_new} for n in user_notifs]

    completed_ids = {c.lesson_id for c in Completion.query.filter_by(user_id=user.id).all()}
    missing_lessons = Lesson.query.filter(~Lesson.id.in_(completed_ids)).count()
    if missing_lessons > 0:
        notifs.insert(0, {
            "id": 0,
            "text": f"You have {missing_lessons} uncompleted lesson(s). Don't miss your learning goal!",
            "is_new": True,
        })

    return notifs


@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("home_page"))
    return redirect(url_for("login"))

@app.route("/home")
def home_page():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    role = session.get("role")
    notifications = []

    if role == "student":
        notifications = get_student_notifications(username)
    else:
        notifications = [{"id": 1, "text": "No notifications yet for lecturers.", "is_new": False}]

    return render_template(
        "home.html",
        title="Home",
        notifications=notifications,
        active_menu="home",
    )

@app.route("/notifications/dismiss/<int:notification_id>")
def dismiss_notification(notification_id):
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    user = User.query.filter_by(username=username).first()
    if not user:
        return redirect(url_for("home_page"))

    notif = Notification.query.filter_by(id=notification_id, user_id=user.id).first()
    if notif:
        notif.is_new = False
        db.session.commit()
        flash("Notification dismissed.", "info")
    return redirect(url_for("home_page"))

@app.route("/notifications/dismiss_all")
def dismiss_all_notifications():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    user = User.query.filter_by(username=username).first()
    if not user:
        return redirect(url_for("home_page"))

    Notification.query.filter_by(user_id=user.id, is_new=True).update({"is_new": False})
    db.session.commit()
    flash("All notifications dismissed.", "info")
    return redirect(url_for("home_page"))

@app.route("/following")
def following_page():
    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=session["username"]).first()
    lecturers = User.query.filter_by(role="lecturer").all()
    profiles = {p.user_id: p for p in LecturerProfile.query.all()}
    saved = {s.lecturer_id for s in SavedLecturer.query.filter_by(user_id=user.id)}

    return render_template(
        "following.html",
        title="Following",
        lecturers=lecturers,
        profiles=profiles,
        saved=saved,
        active_menu="following",
    )

@app.route("/follow/save/<int:lecturer_id>")
def save_lecturer(lecturer_id):
    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return redirect(url_for("following_page"))

    exists = SavedLecturer.query.filter_by(user_id=user.id, lecturer_id=lecturer_id).first()
    if not exists:
        db.session.add(SavedLecturer(user_id=user.id, lecturer_id=lecturer_id))
        db.session.commit()
        flash("Lecturer saved to bucket.", "success")
    else:
        flash("Lecturer already saved.", "info")

    return redirect(url_for("following_page"))

@app.route("/saved")
def saved_lecturers():
    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=session["username"]).first()
    saved_list = SavedLecturer.query.filter_by(user_id=user.id).all()
    lecturer_ids = [s.lecturer_id for s in saved_list]
    lecturers = User.query.filter(User.id.in_(lecturer_ids)).all() if lecturer_ids else []
    profiles = {p.user_id: p for p in LecturerProfile.query.filter(LecturerProfile.user_id.in_(lecturer_ids)).all()} if lecturer_ids else {}

    return render_template("saved.html", title="Saved Lecturers", lecturers=lecturers, profiles=profiles, active_menu="following")

@app.route("/lecturer/<int:lecturer_id>")
def lecturer_profile(lecturer_id):
    if "username" not in session:
        return redirect(url_for("login"))

    lecturer = User.query.filter_by(id=lecturer_id, role="lecturer").first()
    if not lecturer:
        flash("Lecturer not found.", "danger")
        return redirect(url_for("following_page"))

    profile = LecturerProfile.query.filter_by(user_id=lecturer_id).first()
    videos = Video.query.filter_by(lecturer_id=lecturer_id).all()
    comments = Comment.query.filter_by(lecturer_id=lecturer_id).order_by(Comment.created_at.desc()).all()

    return render_template("lecturer_profile.html", title=lecturer.username, lecturer=lecturer, profile=profile, videos=videos, comments=comments, active_menu="following")

@app.route("/video/<int:video_id>")
def video_detail(video_id):
    if "username" not in session:
        return redirect(url_for("login"))

    video = Video.query.get(video_id)
    if not video:
        flash("Video not found.", "danger")
        return redirect(url_for("following_page"))

    user = User.query.filter_by(username=session["username"]).first()
    purchase = Purchase.query.filter_by(user_id=user.id, video_id=video.id, is_active=True).order_by(Purchase.expires_at.desc()).first()

    req_sub = Subscription.query.filter_by(user_id=user.id).filter(Subscription.ends_at > datetime.utcnow()).first()
    lecturer_profile = LecturerProfile.query.filter_by(user_id=video.lecturer_id).first()
    return render_template("video_detail.html", video=video, purchase=purchase, subscription=req_sub, now=datetime.utcnow(), lecturer_profile=lecturer_profile, active_menu="following")

@app.route("/video/<int:video_id>/pay", methods=["GET", "POST"])
def video_pay(video_id):
    if "username" not in session:
        return redirect(url_for("login"))
    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return redirect(url_for("login"))

    video = Video.query.get(video_id)
    if not video:
        flash("Video not found.", "danger")
        return redirect(url_for("following_page"))

    if request.method == "POST":
        option = request.form.get("payment_option")
        now = datetime.utcnow()

        if option in ["quarterly", "yearly"]:
            if option == "quarterly":
                ends_at = now + timedelta(days=90)
            else:
                ends_at = now + timedelta(days=365)
            db.session.add(Subscription(user_id=user.id, type=option, starts_at=now, ends_at=ends_at))
            allowed_mins = max(30, video.duration_min * 2)
        else:
            ends_at = now + timedelta(minutes=max(30, video.duration_min*2))
            allowed_mins = max(30, video.duration_min * 2)

        db.session.add(Purchase(user_id=user.id, video_id=video.id, created_at=now, expires_at=ends_at, is_active=True))
        db.session.commit()
        flash("Payment successful. You can now watch the video.", "success")
        return redirect(url_for("video_watch", video_id=video.id))

    return render_template("video_pay.html", video=video, active_menu="following")

@app.route("/video/<int:video_id>/watch")
def video_watch(video_id):
    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=session["username"]).first()
    video = Video.query.get(video_id)
    if not video:
        flash("Video not found.", "danger")
        return redirect(url_for("following_page"))

    purchase = Purchase.query.filter_by(user_id=user.id, video_id=video.id, is_active=True).order_by(Purchase.expires_at.desc()).first()
    if not purchase or purchase.expires_at < datetime.utcnow():
        flash("Payment is required or session expired.", "danger")
        return redirect(url_for("video_pay", video_id=video.id))

    remaining_seconds = int((purchase.expires_at - datetime.utcnow()).total_seconds())
    return render_template("video_watch.html", video=video, remaining_seconds=remaining_seconds, active_menu="following")

@app.route("/comment/<int:lecturer_id>", methods=["POST"])
def add_comment(lecturer_id):
    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=session["username"]).first()
    text = request.form.get("comment_text", "").strip()
    if text:
        db.session.add(Comment(user_id=user.id, lecturer_id=lecturer_id, text=text))
        db.session.commit()
        flash("Comment submitted.", "success")
    return redirect(url_for("lecturer_profile", lecturer_id=lecturer_id))

@app.route("/help")
def help_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("page.html", title="Help", content="Need help? Email support@example.com.", active_menu="help")

@app.route("/practiced")
def practiced_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("page.html", title="Practiced Questions", content="View previously practiced questions.", active_menu="practiced")

@app.route("/queries")
def queries_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("page.html", title="Queries", content="Ask your lecturer questions.", active_menu="queries")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        user = User.query.filter_by(username=username, role=role).first()
        if user and user.password == password:
            session["username"] = username
            session["role"] = role
            flash(f"Logged in as {role.title()}: {username}", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials or role mismatch.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    role = session.get("role")

    if role == "lecturer" and request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if title and content:
            db.session.add(Lesson(title=title, content=content))
            db.session.commit()
            flash("Lesson added.", "success")
        else:
            flash("Lesson title and content are required.", "danger")

    # Period selection for students: day/week/month
    selected_period = request.args.get("period", "day")
    if selected_period not in ["day", "week", "month"]:
        selected_period = "day"

    # static learning time values for demo; replace with computed data later
    learning_time = {
        "day": 2.5,
        "week": 12.0,
        "month": 48.0,
    }

    student_progress = []
    if role == "student":
        user = User.query.filter_by(username=username).first()
        if user:
            student_progress = [c.lesson_id for c in Completion.query.filter_by(user_id=user.id).all()]

    # get all lessons
    lessons = Lesson.query.order_by(Lesson.id).all()

    return render_template(
        "dashboard.html",
        username=username,
        role=role,
        lessons=lessons,
        progress=student_progress,
        selected_period=selected_period,
        learning_time=learning_time,
        active_menu="dashboard",
    )

@app.route("/complete/<int:lesson_id>")
def complete_lesson(lesson_id):
    if "username" not in session or session.get("role") != "student":
        flash("Only students can mark lessons completed.", "danger")
        return redirect(url_for("dashboard"))

    username = session["username"]
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    already_done = Completion.query.filter_by(user_id=user.id, lesson_id=lesson_id).first()
    if not already_done:
        db.session.add(Completion(user_id=user.id, lesson_id=lesson_id))
        db.session.commit()
        flash("Lesson marked as completed.", "success")
    else:
        flash("Lesson already completed.", "info")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)

