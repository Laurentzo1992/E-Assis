from django.urls import path
from .views import scraping_control_view

urlpatterns = [
    path('', scraping_control_view, name='scraping_control'),
]
