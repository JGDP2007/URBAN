from flask import Flask
from models import db
from flask_login import LoginManager
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from flask_apscheduler import APScheduler
from flask import Flask, send_from_directory

app = Flask(__name__)

# ---------------- CONFIG ----------------
app.config['SECRET_KEY'] = 'secret123'
import os

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') , 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_TIMEZONE'] = 'Africa/Johannesburg'

import os

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- EMAIL ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'urbanappreminder@gmail.com'
app.config['MAIL_PASSWORD'] = 'umao kxsm roow ygfm'
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# ---------------- DB ----------------
db.init_app(app)

# ---------------- LOGIN ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

from models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- ROUTES ----------------
from routes import *

# ---------------- CREATE DB ----------------
with app.app_context():
    db.create_all()

# ---------------- EMAIL REMINDERS ----------------

def send_automated_reminders():
    from models import Task, User

    with app.app_context():
        now = datetime.now()

        tasks = Task.query.filter(
            Task.completed == False,
            Task.reminder_time != None
        ).all()

        for task in tasks:
            user = db.session.get(User, task.assigned_to)

            if not user or not user.email:
                continue

            # ✅ ONLY use reminder_time (your new system)
            if now >= task.reminder_time:
                try:
                    msg = Message(
                        subject=f"REMINDER: {task.title}",
                        recipients=[user.email]
                    )

                    msg.body = f"""
Hello {user.name},

Reminder: {task.title}
Frequency: {task.frequency}

https://YOUR-APP-NAME.onrender.com/project/{task.project_id}
"""

                    mail.send(msg)
                    print(f"Sent to {user.email}")

                except Exception as e:
                    print(f"Email error: {e}")

                # 🔁 RESCHEDULE BASED ON FREQUENCY
                if task.frequency == "Once":
                    task.reminder_time = None

                elif task.frequency == "Daily":
                    task.reminder_time += timedelta(days=1)

                elif task.frequency == "Weekly":
                    task.reminder_time += timedelta(weeks=1)

                elif task.frequency == "Monthly":
                    task.reminder_time += timedelta(days=30)  # simple version

        db.session.commit()
        
# ---------------- SCHEDULER ----------------
scheduler = APScheduler()
scheduler.init_app(app)

scheduler.add_job(
    id='reminders',
    func=send_automated_reminders,
    trigger='interval',
    minutes=1   # 🔥 runs every minute
)

import os

if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler.start()      
# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()