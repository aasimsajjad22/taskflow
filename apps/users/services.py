from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.users.models import User


def user_create(*, email: str, password: str, first_name: str = "", last_name: str = "") -> User:

    email = User.objects.normalize_email(email)
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError("User with this email already exists.")

    user = User(email=email, first_name=first_name, last_name=last_name)

    try:
        validate_password(password)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from error

    user.set_password(password)
    user.save()

    return user


def user_update_profile(*, user: User, data: dict) -> User:
    allowed_fields = ["first_name", "last_name"]

    changed = []
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
            changed.append(field)

    if changed:
        user.save(update_fields=changed)

    return user


def user_change_password(*, user: User, old_password: str, new_password: str) -> User:
    if not user.check_password(old_password):
        raise ValidationError("Your current password is wrong.")

    try:
        validate_password(new_password)
    except ValidationError as error:
        raise ValidationError({"new_password": error.messages}) from error

    user.set_password(new_password)

    user.save(update_fields=["password"])

    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
