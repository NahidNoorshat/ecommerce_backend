from .base import *

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_grocery',    # ✅ your local db name
        'USER': 'postgres',              # ✅ your local db user
        'PASSWORD': 'nahid123',           # ✅ your local db password
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# development.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'channels': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'django.channels': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}