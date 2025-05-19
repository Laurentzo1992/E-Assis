from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EntrepriseViewSet, DomaineViewSet, SecteurActiviteViewSet

router = DefaultRouter()
router.register(r'entreprises', EntrepriseViewSet)
router.register(r'domaines', DomaineViewSet)
router.register(r'secteurs', SecteurActiviteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
