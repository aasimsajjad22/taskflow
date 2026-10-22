# settings: for FRONTEND_URL.
from django.conf import settings

# EmailMultiAlternatives: an email with a plain-text body plus an HTML version.
from django.core.mail import EmailMultiAlternatives

# render_to_string: fill a template with data and return the result as text.
from django.template.loader import render_to_string


# Build and send the "you were assigned a task" email. Runs SYNCHRONOUSLY:
# it talks to the SMTP server right now and waits for it.
def email_task_assigned(*, task) -> None:
    # The data the two templates can use.
    context = {
        "task": task,
        "project": task.project,
        "assignee": task.assignee,
        # A link to the task in the frontend.
        "task_url": f"{settings.FRONTEND_URL}/tasks/{task.id}",
    }
    # The subject line, e.g. "[WEB] You were assigned: Fix login".
    subject = f"[{task.project.key}] You were assigned: {task.title}"
    # Fill both templates.
    text_body = render_to_string("projects/emails/task_assigned.txt", context)
    html_body = render_to_string("projects/emails/task_assigned.html", context)
    # Build the email. The "From" address comes from DEFAULT_FROM_EMAIL.
    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[task.assignee.email])
    # Add the HTML version. Email apps show HTML if they can, else the text.
    message.attach_alternative(html_body, "text/html")
    # Connect to the SMTP server and send. Raises an error if the server is down.
    message.send()


# Build and send the daily "your overdue tasks" email to one user.
# tasks = the first few overdue tasks to list; total = how many there are in total.
def email_overdue_digest(*, user, tasks, total: int) -> None:
    # The data for the templates.
    context = {
        "user": user,
        "tasks": tasks,
        "total": total,
        # A link to the full overdue list in the frontend.
        "overdue_url": f"{settings.FRONTEND_URL}/tasks?overdue=true&assigned_to_me=true",
    }
    # e.g. "You have 37 overdue tasks"
    subject = f"You have {total} overdue task{'s' if total != 1 else ''}"
    # Fill both templates.
    text_body = render_to_string("projects/emails/overdue_digest.txt", context)
    html_body = render_to_string("projects/emails/overdue_digest.html", context)
    # Build the email with text + HTML.
    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[user.email])
    message.attach_alternative(html_body, "text/html")
    # Send it.
    message.send()
