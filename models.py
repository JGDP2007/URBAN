from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# ---------------- USER ----------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="user")

    comments = db.relationship('Comment', backref='user', lazy=True)

    assigned_projects = db.relationship('Project', backref='assigned_user', lazy=True)
    assigned_tasks = db.relationship('Task', backref='assigned_user', lazy=True)


# ---------------- PROJECT ----------------
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))
    description = db.Column(db.Text)

    created_by = db.Column(db.Integer)

    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))

    deadline = db.Column(db.DateTime)
    reminder_time = db.Column(db.DateTime)
    frequency = db.Column(db.String(20))

    archived = db.Column(db.Boolean, default=False)

    # ✅ cascade delete tasks when project deleted
    tasks = db.relationship(
        'Task',
        backref='project',
        cascade="all, delete-orphan"
    )


# ---------------- TASK ----------------
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(
        db.Integer,
        db.ForeignKey('project.id', ondelete="CASCADE")
    )

    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    due_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)

    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))

    frequency = db.Column(db.String(50))
    reminder_time = db.Column(db.DateTime, nullable=True)

    # ✅ cascade delete attachments + comments
    attachments = db.relationship(
        'Attachment',
        backref='task',
        cascade="all, delete-orphan"
    )

    comments = db.relationship(
        'Comment',
        backref='task',
        cascade="all, delete-orphan"
    )


# ---------------- ATTACHMENT ----------------
class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(
        db.Integer,
        db.ForeignKey('task.id', ondelete="CASCADE"),
        nullable=False
    )

    filename = db.Column(db.String(200))
    filepath = db.Column(db.String(300))
    link = db.Column(db.String(300))

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------- COMMENT ----------------
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    task_id = db.Column(
        db.Integer,
        db.ForeignKey('task.id', ondelete="CASCADE")
    )