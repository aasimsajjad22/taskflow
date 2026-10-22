# factory: the factory_boy library. DjangoModelFactory saves objects with the Django ORM.
import factory
from factory.django import DjangoModelFactory

# Our User model.
from apps.users.models import User


# Builds User rows for tests. Like a Laravel UserFactory.
class UserFactory(DjangoModelFactory):
    # Which model this factory creates.
    class Meta:
        model = User

    # A unique email for every user: user1@example.com, user2@example.com, ...
    # Sequence = a counter that goes up by one for each object.
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    # Faker: a realistic random first name ("Sara", "Omar"...).
    first_name = factory.Faker("first_name")
    # A known password, HASHED like Django does it, so tests can log in with "Pass-12345".
    password = factory.django.Password("Pass-12345")
