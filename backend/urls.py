# /backend/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PublicationViewSet, TypeProcedureViewSet, MarcheViewSet, AppelOffreViewSet,
    ResultatViewSet, LotViewSet, DomaineViewSet, PublicationDomaineViewSet,
    AlerteViewSet, NotificationViewSet, MarcheDetailViewSet
)

# Initialisation du routeur
router = DefaultRouter()

# Enregistrement de toutes les routes sans préfixe
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'alertes', AlerteViewSet, basename='alerte')
router.register(r'publications', PublicationViewSet, basename='publication') # Ajout du basename par sécurité
router.register(r'types-procedure', TypeProcedureViewSet, basename='typeprocedure')
router.register(r'marches', MarcheViewSet, basename='marche')
router.register(r'appels-offres', AppelOffreViewSet, basename='appeloffre')
router.register(r'resultats', ResultatViewSet, basename='resultat')
router.register(r'lots', LotViewSet, basename='lot')
router.register(r'domaines', DomaineViewSet, basename='domaine')
router.register(r'publications-domaines', PublicationDomaineViewSet, basename='publicationdomaine')
router.register(r'marches-details', MarcheDetailViewSet, basename='marche-detail')

urlpatterns = [
    path('', include(router.urls)),
]