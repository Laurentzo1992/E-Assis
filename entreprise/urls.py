from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomaineViewSet, SecteurActiviteViewSet, EntrepriseViewSet

router = DefaultRouter()
router.register(r'domaines', DomaineViewSet, basename='domaine')
router.register(r'secteurs', SecteurActiviteViewSet, basename='secteur')
router.register(r'entreprises', EntrepriseViewSet, basename='entreprise')

urlpatterns = [
    path('', include(router.urls)),
]
