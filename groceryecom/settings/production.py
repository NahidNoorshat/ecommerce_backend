from .base import *

DEBUG = False

ALLOWED_HOSTS = ["api.hairin.xyz"]

CSRF_TRUSTED_ORIGINS = [
    "https://api.hairin.xyz",
    "https://site.hairin.xyz",
]

CORS_ALLOWED_ORIGINS = [
    "https://site.hairin.xyz",
    "https://ecommerce-neon-mu.vercel.app",
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config("DB_NAME"),
        'USER': config("DB_USER"),
        'PASSWORD': config("DB_PASSWORD"),
        'HOST': config("DB_HOST"),
        'PORT': config("DB_PORT"),
    }
}

# 👇 Add this block for best production practice
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
