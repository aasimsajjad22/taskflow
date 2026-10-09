from .base import *

# Tests never need debug pages.
DEBUG = False
# Use a very fast (and weak) password hasher.
# Real hashers are slow ON PURPOSE, which makes tests with many users slow.
# NEVER use this outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
