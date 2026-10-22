# factory_boy.
import factory
from factory.django import DjangoModelFactory

# Other factories and our models.
from apps.projects.models import Project, Task
from apps.workspaces.factories import WorkspaceFactory


# Builds Project rows.
class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    # A new workspace (with its owner), unless the test passes one.
    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"Project {n}")
    # Keys must be unique per workspace: P1, P2, ...
    key = factory.Sequence(lambda n: f"P{n}")
    # SelfAttribute: take the value from another field. Here: the workspace's owner.
    created_by = factory.SelfAttribute("workspace.owner")


# Builds Task rows.
class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    # A new project (with workspace and owner), unless the test passes one.
    project = factory.SubFactory(ProjectFactory)
    # A random short sentence like "Fix the login page".
    title = factory.Faker("sentence", nb_words=4)
    # The workspace owner reported it (two dots: project -> workspace -> owner).
    reporter = factory.SelfAttribute("project.workspace.owner")
    status = Task.Status.TODO
    priority = Task.Priority.MEDIUM
