from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PublicationViewSet, TypeProcedureViewSet, MarcheViewSet, AppelOffreViewSet,
    ResultatViewSet, LotViewSet, DomaineViewSet, PublicationDomaineViewSet, AlerteViewSet
)

router = DefaultRouter()
router.register(r'publications', PublicationViewSet)
router.register(r'types-procedure', TypeProcedureViewSet)
router.register(r'marches', MarcheViewSet)
router.register(r'appels-offres', AppelOffreViewSet)
router.register(r'resultats', ResultatViewSet)
router.register(r'lots', LotViewSet)
router.register(r'domaines', DomaineViewSet)
router.register(r'publications-domaines', PublicationDomaineViewSet)
router.register(r'alertes', AlerteViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
