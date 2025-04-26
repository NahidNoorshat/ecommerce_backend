from .base import *

DEBUG = False

ALLOWED_HOSTS = ["api.hairin.xyz"]

CSRF_TRUSTED_ORIGINS = [
    "https://api.hairin.xyz",
    "https://site.hairin.xyz",  # if you use frontend subdomain later
]

CORS_ALLOWED_ORIGINS = [
    "https://site.hairin.xyz",
    "https://ecommerce-neon-mu.vercel.app",  # your current frontend in vercel
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
