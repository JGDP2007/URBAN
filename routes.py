from flask import render_template, redirect, url_for, request, Response, send_file
from app import app, mail
from models import db, User, Project, Task, Attachment, Comment
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message
from werkzeug.utils import secure_filename
import base64
import os
from datetime import datetime, date, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


# ---------------- LANDING PAGE ----------------
@app.route("/")
def landing():
    return render_template("landing.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    ADMIN_SECRET = "ADMIN123"

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        admin_key = request.form.get("admin_key")

        if User.query.filter_by(email=email).first():
            return "Email already exists", 400

        role = "admin" if admin_key == ADMIN_SECRET else "user"

        user = User(name=name, email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email")).first()

        if user and user.password == request.form.get("password"):
            login_user(user)
            return redirect(url_for("dashboard"))

    return render_template("login.html")


# ---------------- EMAIL ----------------
def send_assignment_email(user, item_name, frequency):
    try:
        msg = Message(
            subject=f"New Assignment: {item_name}",
            recipients=[user.email]
        )

        msg.body = f"""Hello {user.name},

You have been assigned: {item_name}
Reminder: {frequency}

Check dashboard.
"""
        mail.send(msg)

    except Exception as e:
        print(f"Email error: {e}")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()

    if current_user.role == "admin":
        all_projects = Project.query.all()
    else:
        direct_projects = Project.query.filter_by(assigned_to=current_user.id).all()
        user_tasks = Task.query.filter_by(assigned_to=current_user.id).all()
        task_project_ids = list(set([t.project_id for t in user_tasks]))
        task_projects = Project.query.filter(Project.id.in_(task_project_ids)).all()
        all_projects = list({p.id: p for p in (direct_projects + task_projects)}.values())

    active_projects = []
    completed_projects = []

    # ✅ LOOP BACK (this was missing)
    for p in all_projects:
        if p.archived:
            continue

        tasks = Task.query.filter_by(project_id=p.id).all()

        total = len(tasks)
        done = len([t for t in tasks if t.completed])
        p.progress = int((done / total) * 100) if total > 0 else 0

        # time left logic
        if p.deadline:
            diff = (p.deadline.date() - today).days
            if diff > 0:
                p.time_left = f"{diff} days left"
            elif diff == 0:
                p.time_left = "Due today"
            else:
                p.time_left = "Overdue"
        else:
            p.time_left = "No deadline"

        # split active vs completed
        if p.progress == 100:
            completed_projects.append(p)
        else:
            active_projects.append(p)

    # SORT + LIMIT
    completed_projects.sort(key=lambda x: x.id, reverse=True)
    visible_completed = completed_projects[:5]
    archived_projects = completed_projects[5:]

    for p in archived_projects:
        if not p.archived:
            p.archived = True

    db.session.commit()

    return render_template(
    "dashboard.html",
    active_projects=active_projects,
    completed_projects=visible_completed,
    users=User.query.all(),
    user=current_user,
    now=datetime.now().strftime("%Y-%m-%dT%H:%M")
)
# ---------------- PROJECT PAGE ----------------
@app.route("/project/<int:id>")
@login_required
def project(id):
    project = Project.query.get_or_404(id)

    tasks = Task.query.filter_by(project_id=id).all()
    today = date.today()

    for t in tasks:
        if t.due_date:
            diff = (t.due_date.date() - today).days
            t.days_left = f"{diff} days left" if diff > 0 else ("Due today" if diff == 0 else "Overdue")
        else:
            t.days_left = "No date"

    total = len(tasks)
    done = len([t for t in tasks if t.completed])
    progress = int((done / total) * 100) if total > 0 else 0


    return render_template(
    "project.html",
    project=project,
    tasks=tasks,
    progress=progress,
    users=User.query.all(),
    user=current_user,
    now=datetime.now().strftime("%Y-%m-%dT%H:%M")  # 👈 ADD THIS
)


# ---------------- CREATE TASK ----------------
@app.route("/create_task/<int:project_id>", methods=["POST"])
@login_required
def create_task(project_id):

    due_date_raw = request.form.get("due_date")
    reminder_raw = request.form.get("reminder_time")

    # ✅ PARSE DUE DATE
    due_date = None
    if due_date_raw:
        try:
            due_date = datetime.fromisoformat(due_date_raw)
        except Exception:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d")

    # ✅ PARSE REMINDER TIME (SEPARATE)
    reminder_time = None
    if reminder_raw:
        try:
            reminder_time = datetime.fromisoformat(reminder_raw)
        except Exception:
            reminder_time = None

    # ✅ CREATE TASK
    task = Task(
        title=request.form.get("title"),
        description=request.form.get("description"),
        project_id=project_id,
        assigned_to=int(request.form.get("assigned_to")) if request.form.get("assigned_to") else None,
        frequency=request.form.get("frequency"),
        due_date=due_date,
        completed=False,
        reminder_time=reminder_time   # 🔥 FIXED
    )

    db.session.add(task)
    db.session.commit()

    # ✅ SEND EMAIL
    if task.assigned_to:
        user = User.query.get(task.assigned_to)
        if user:
            send_assignment_email(user, task.title, task.frequency)

    return redirect(url_for("project", id=project_id))

# ---------------- COMPLETE TASK ----------------
@app.route("/complete_task/<int:task_id>")
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.completed = True
    db.session.commit()

    return redirect(url_for("project", id=task.project_id))


# ---------------- DELETE TASK ----------------
@app.route("/delete_task/<int:task_id>")
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()

    return redirect(url_for("project", id=task.project_id))


# ---------------- CREATE PROJECT ----------------
@app.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    from datetime import datetime

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        assigned_to = request.form.get("assigned_to")

        deadline_raw = request.form.get("deadline")
        reminder_raw = request.form.get("reminder_time")
        frequency = request.form.get("frequency")

        # Parse deadline
        deadline = None
        if deadline_raw:
            try:
                deadline = datetime.fromisoformat(deadline_raw)
            except ValueError:
                deadline = None

        # Parse reminder
        reminder_time = None
        if reminder_raw:
            try:
                reminder_time = datetime.fromisoformat(reminder_raw)
            except ValueError:
                reminder_time = None

        assigned_to_id = int(assigned_to) if assigned_to else None

        project = Project(
            name=name,
            description=description,
            created_by=current_user.id,
            assigned_to=assigned_to_id,
            deadline=deadline,
            reminder_time=reminder_time,
            frequency=frequency
        )

        db.session.add(project)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("create_project.html")
# ---------------- DELETE PROJECT ----------------
@app.route("/delete_project/<int:project_id>")
@login_required
def delete_project(project_id):
    Task.query.filter_by(project_id=project_id).delete()
    Project.query.filter_by(id=project_id).delete()
    db.session.commit()

    return redirect(url_for("dashboard"))


# ---------------- ADD COMMENT ----------------
@app.route("/add_comment/<int:task_id>", methods=["POST"])
@login_required
def add_comment(task_id):
    comment = Comment(
        content=request.form.get("content"),
        user_id=current_user.id,
        task_id=task_id
    )

    db.session.add(comment)
    db.session.commit()

    return redirect(request.referrer)


# ---------------- MY TASKS ----------------
@app.route("/my_tasks")
@login_required
def my_tasks():
    tasks = Task.query.filter_by(assigned_to=current_user.id).all()
    return render_template("my_tasks.html", tasks=tasks, user=current_user)


# ---------------- EXPORT PROJECT PDF ----------------
from io import BytesIO

@app.route("/export_project_pdf/<int:project_id>")
@login_required
def export_project_pdf(project_id):
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project_id).all()

    buffer = BytesIO()  # ✅ in-memory file

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer)

    content = [
        Paragraph(f"Project: {project.name}", styles["Title"]),
        Spacer(1, 10)
    ]

    for t in tasks:
        status = "✔ Completed" if t.completed else "✖ Pending"
        content.append(Paragraph(f"- {t.title} ({status})", styles["Normal"]))

    doc.build(content)

    buffer.seek(0)  # 🔥 important

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"project_{project.id}.pdf",
        mimetype="application/pdf"
    )
# ---------------- EXPORT TASK PDF ----------------
from io import BytesIO

@app.route("/export-task/<int:task_id>")
@login_required
def export_task_pdf(task_id):
    task = Task.query.get_or_404(task_id)

    buffer = BytesIO()

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer)

    status = "Completed" if task.completed else "Pending"

    content = [
        Paragraph(f"Task: {task.title}", styles["Title"]),
        Paragraph(f"Description: {task.description or 'No description'}", styles["Normal"]),
        Paragraph(f"Status: {status}", styles["Normal"])
    ]

    doc.build(content)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"task_{task.id}.pdf",
        mimetype="application/pdf"
    )
# ---------------- UPLOAD TASK ----------------
@app.route("/upload_task/<int:task_id>", methods=["POST"])
@login_required
def upload_task(task_id):
    task = Task.query.get_or_404(task_id)

    file = request.files.get("file")
    link = request.form.get("link")

    if file and file.filename:
        upload_folder = os.path.join("static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        db.session.add(Attachment(filename=filename, filepath=filepath, task_id=task_id))

    elif link:
        db.session.add(Attachment(link=link, task_id=task_id))

    db.session.commit()
    return redirect(url_for("project", id=task.project_id))


# ---------------- SAVE DRAWING ----------------
@app.route("/save_drawing/<int:task_id>", methods=["POST"])
@login_required
def save_drawing(task_id):
    try:
        data = request.get_json()
        image_data = data.get("image")

        if not image_data:
            return {"success": False}

        image_data = base64.b64decode(image_data.split(",")[1])

        upload_folder = os.path.join("static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        filename = f"drawing_{int(datetime.now().timestamp())}.png"
        filepath = os.path.join(upload_folder, filename)

        with open(filepath, "wb") as f:
            f.write(image_data)

        db.session.add(Attachment(task_id=task_id, filename=filename, filepath=filepath))
        db.session.commit()

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}
# ---------------- UPDATE TASK ASSIGNMENT ----------------
@app.route("/update_task_assignment/<int:task_id>", methods=["POST"])
@login_required
def update_task_assignment(task_id):
    task = Task.query.get_or_404(task_id)

    new_user_id = request.form.get("assigned_to")

    if new_user_id and new_user_id.isdigit():
        task.assigned_to = int(new_user_id)
    else:
        task.assigned_to = None

    db.session.commit()

    return redirect(url_for("project", id=task.project_id))
# ---------------- UPDATE PROJECT ASSIGNMENT ----------------
@app.route("/update_project_assignment/<int:project_id>", methods=["POST"])
@login_required
def update_project_assignment(project_id):
    project = Project.query.get_or_404(project_id)

    new_user_id = request.form.get("assigned_to")

    if new_user_id and new_user_id.isdigit():
        project.assigned_to = int(new_user_id)
    else:
        project.assigned_to = None

    db.session.commit()

    return redirect(url_for("project", id=project_id))
# ------archive project----------------
@app.route("/archive")
@login_required
def archive():
    projects = Project.query.filter_by(archived=True).all()

    return render_template(
        "archive.html",
        projects=projects,
        user=current_user
    )
    
#------------------ Delete Attchment ----------------
@app.route("/delete_attachment/<int:attachment_id>")
def delete_attachment(attachment_id):
    from models import Attachment
    import os

    attachment = Attachment.query.get_or_404(attachment_id)

    # 🔐 Optional: permission check
    # only admin OR assigned user
    from flask_login import current_user
    if current_user.role != "admin" and attachment.task.assigned_to != current_user.id:
        return "Unauthorized", 403

    # 🗑️ delete file from disk
    if attachment.filepath:
        file_path = os.path.join("static/uploads", attachment.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    # 🗑️ delete from DB
    db.session.delete(attachment)
    db.session.commit()

    return redirect(request.referrer)
# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

