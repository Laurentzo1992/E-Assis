from django.urls import path, include
from .views import scraping_control_view
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet)


urlpatterns = [
    path('', scraping_control_view, name='scraping_control'),
    path('api/', include(router.urls)),
]
