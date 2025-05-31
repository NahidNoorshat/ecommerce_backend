# asgi.py
import os
from decouple import config

# 1. Set default settings first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", config("DJANGO_SETTINGS_MODULE", default="groceryecom.settings.development"))

# 2. Initialize Django
import django
django.setup()

# 3. Now import other Django-dependent modules
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

# Import routing after Django setup
try:
    import notifications.routing
    import chat.routing
    
    # Debug routes
    combined_routes = (
        getattr(notifications.routing, 'websocket_urlpatterns', []) + 
        getattr(chat.routing, 'websocket_urlpatterns', [])
    )
    print("Loaded WebSocket routes:")
    for route in combined_routes:
        print(f"- {route.pattern}")
except Exception as e:
    print(f"Error loading WebSocket routes: {e}")
    raise

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(combined_routes)
    ),
})