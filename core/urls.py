from django.urls import path
from .views import health_check

urlpatterns = [
    path("health-check/", health_check),
]
