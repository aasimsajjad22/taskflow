# Create your tests here.
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_create_user_with_email_address():
    user = User.objects.create_user(email="Sajjad@EXAMPLE.com", password="password")

    assert user.email == "Sajjad@example.com"

    assert user.check_password("password")

    assert user.is_staff is False

    assert user.is_superuser is False

    assert str(user) == "Sajjad@example.com"


# Superuser creation test.
@pytest.mark.django_db
def test_create_superuser():
    # Create an admin user.
    admin = User.objects.create_superuser(email="admin@example.com", password="strong-pass-123")
    # Admin can access the admin panel.
    assert admin.is_staff is True
    # Admin has all permissions.
    assert admin.is_superuser is True


# This test needs no database: the error happens before saving.
def test_create_user_without_email_fails():
    # pytest.raises checks that the code inside raises ValueError.
    # Like $this->expectException(ValueError::class) in PHPUnit.
    with pytest.raises(ValueError):
        # Empty email must be rejected.
        User.objects.create_user(email="", password="strong-pass-123")
