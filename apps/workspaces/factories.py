# factory_boy.
import factory
from factory.django import DjangoModelFactory

# Other factories and our models.
from apps.users.factories import UserFactory
from apps.workspaces.models import Membership, Workspace


# Builds Workspace rows. Like the workspace_create service, it also makes the owner a member.
class WorkspaceFactory(DjangoModelFactory):
    class Meta:
        model = Workspace
        # Our post-generation hook below saves its own row (the membership), so factory_boy
        # doesn't need to save the workspace a second time afterwards.
        skip_postgeneration_save = True

    # "Workspace 1", "Workspace 2", ... and matching unique slugs.
    name = factory.Sequence(lambda n: f"Workspace {n}")
    slug = factory.Sequence(lambda n: f"workspace-{n}")
    # SubFactory: create a new User for the owner (unless the test passes one).
    owner = factory.SubFactory(UserFactory)

    # Runs AFTER the workspace is saved. Our app expects every owner to be a member too.
    @factory.post_generation
    def owner_membership(workspace, create, extracted, **kwargs):
        # create is False for WorkspaceFactory.build() (an unsaved object): nothing to do then.
        if create:
            Membership.objects.create(
                workspace=workspace, user=workspace.owner, role=Membership.Role.OWNER
            )


# Builds Membership rows: a user in a workspace with a role (member by default).
class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    # A new workspace and a new user, unless the test passes them.
    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER
