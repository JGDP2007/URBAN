from datetime import datetime, timedelta
from app import app
from models import db, Task, Project

# Optional (better monthly handling)
from dateutil.relativedelta import relativedelta


def check_reminders():
    with app.app_context():
        now = datetime.now()

        # -------- TASKS --------
        tasks = Task.query.filter(Task.reminder_time != None).all()

        for task in tasks:
            if task.reminder_time and task.reminder_time <= now:
                print(f"[TASK REMINDER] {task.title}")

                # 👉 TODO: send email / notification here

                # Handle frequency
                if task.frequency == "Once":
                    task.reminder_time = None

                elif task.frequency == "Daily":
                    task.reminder_time += timedelta(days=1)

                elif task.frequency == "Weekly":
                    task.reminder_time += timedelta(weeks=1)

                elif task.frequency == "Monthly":
                    task.reminder_time += relativedelta(months=1)

        # -------- PROJECTS --------
        projects = Project.query.filter(Project.reminder_time != None).all()

        for project in projects:
            if project.reminder_time and project.reminder_time <= now:
                print(f"[PROJECT REMINDER] {project.name}")

                # 👉 TODO: send email / notification here

                if project.frequency == "Once":
                    project.reminder_time = None

                elif project.frequency == "Daily":
                    project.reminder_time += timedelta(days=1)

                elif project.frequency == "Weekly":
                    project.reminder_time += timedelta(weeks=1)

                elif project.frequency == "Monthly":
                    project.reminder_time += relativedelta(months=1)

        db.session.commit()


# 🔁 RUN LOOP
if __name__ == "__main__":
    import time

    while True:
        check_reminders()
        time.sleep(60)  # check every minute