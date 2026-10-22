# random: pick random values for the fake data.
import random

# timedelta: a length of time, for due dates and completion times.
from datetime import timedelta

# Get our User model.
from django.contrib.auth import get_user_model

# BaseCommand: parent class for all management commands (like Laravel's Command class).
from django.core.management.base import BaseCommand

# transaction.atomic: all inserts succeed together, or nothing is saved.
from django.db import transaction

# timezone.now() / localdate(): the current time and date.
from django.utils import timezone

# Our models and services.
from apps.projects.models import Comment, Project, Task
from apps.workspaces.services import membership_add, workspace_create

# The User model class.
User = get_user_model()

# Password for all demo users, so you can log in as any of them.
DEMO_PASSWORD = "Demo-Pass-123"

# Words used to build random task titles like "Fix payment #42".
VERBS = ["Fix", "Build", "Refactor", "Test", "Design", "Review", "Update", "Remove"]
WORDS = ["login", "signup", "dashboard", "payment", "invoice", "report", "search", "profile"]

# The demo projects: (name, key).
PROJECTS = [("Website", "WEB"), ("Mobile App", "MOB"), ("API", "API"), ("Ops", "OPS")]


# "python manage.py seed_demo" runs this class. Like a Laravel seeder.
class Command(BaseCommand):
    # Shown by "python manage.py help seed_demo".
    help = "Create a demo workspace with members, projects, many tasks, and comments."

    # Extra command-line options. Like {--tasks=5000} in a Laravel command signature.
    def add_arguments(self, parser):
        # --tasks 20000 -> options["tasks"] == 20000
        parser.add_argument("--tasks", type=int, default=5000, help="How many tasks to create.")

    # Get a user by email, or create one with the demo password.
    def _get_or_create_user(self, email):
        # Look for an existing user first, so running the command twice works.
        user = User.objects.filter(email=email).first()
        # Not found: create it.
        if user is None:
            user = User.objects.create_user(email=email, password=DEMO_PASSWORD)
        # Return the user.
        return user

    # The main method. Django calls it when the command runs.
    # @transaction.atomic: if anything fails, no half-created data is left behind.
    @transaction.atomic
    def handle(self, *args, **options):
        # Same "random" choices every run, so everyone gets the same demo data.
        random.seed(42)

        # One owner and five members.
        owner = self._get_or_create_user("demo-owner@example.com")
        members = [self._get_or_create_user(f"demo-member{i}@example.com") for i in range(1, 6)]

        # A workspace (owner becomes its owner-member) and the members.
        workspace = workspace_create(name="Demo Company", owner=owner)
        for member in members:
            membership_add(workspace=workspace, user=member)

        # Everyone who can be an assignee or reporter.
        people = [owner, *members]

        # Four projects. A few rows, so normal create() is fine here.
        projects = [
            Project.objects.create(workspace=workspace, name=name, key=key, created_by=owner)
            for name, key in PROJECTS
        ]

        # (Tasks come in the next step.)
        self.stdout.write(f"Workspace {workspace.id} with {len(projects)} projects created.")

        # Today and now, used for due dates and completion times.
        today = timezone.localdate()
        now = timezone.now()

        # Build all Task objects IN MEMORY first. Nothing is saved yet.
        tasks = []
        for number in range(1, options["tasks"] + 1):
            # About 40% todo, 20% in progress, 40% done.
            status = random.choices(
                [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE], weights=[4, 2, 4]
            )[0]
            # 80% of tasks have a due date between 30 days ago and 30 days from now.
            due_date = None
            if random.random() < 0.8:
                due_date = today + timedelta(days=random.randint(-30, 30))
            # Done tasks get a completion time in the last 40 days.
            completed_at = None
            if status == Task.Status.DONE:
                days_ago = timedelta(days=random.randint(0, 40), hours=random.randint(0, 23))
                completed_at = now - days_ago
            # Add the (unsaved) task to the list.
            tasks.append(
                Task(
                    project=random.choice(projects),
                    title=f"{random.choice(VERBS)} {random.choice(WORDS)} #{number}",
                    status=status,
                    priority=random.choice([1, 2, 3]),
                    # Some tasks have no assignee (None).
                    assignee=random.choice([*people, None]),
                    reporter=random.choice(people),
                    due_date=due_date,
                    completed_at=completed_at,
                )
            )

        # Save ALL tasks with a few big INSERT queries (1000 rows per query).
        # One create() per task would mean thousands of separate queries.
        Task.objects.bulk_create(tasks, batch_size=1000)

        # Comments on about 30% of the tasks. On PostgreSQL, bulk_create fills in
        # each task's id, so we can use the tasks here.
        comments = [
            Comment(task=task, author=random.choice(people), body="Working on it.")
            for task in tasks
            if random.random() < 0.3
        ]
        # Save all comments in bulk too.
        Comment.objects.bulk_create(comments, batch_size=1000)

        # Print a green success message in the terminal.
        self.stdout.write(
            self.style.SUCCESS(
                f"Workspace {workspace.id} '{workspace.name}': {len(tasks)} tasks, "
                f"{len(comments)} comments. Log in as {owner.email} / {DEMO_PASSWORD}"
            )
        )
