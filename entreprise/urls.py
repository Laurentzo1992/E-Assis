from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomaineViewSet, SecteurActiviteViewSet, EntrepriseViewSet  ,ActiveEntrepriseAPIView

router = DefaultRouter()
router.register(r'domaines', DomaineViewSet, basename='domaine')
router.register(r'secteurs', SecteurActiviteViewSet, basename='secteur')
router.register(r'entreprises', EntrepriseViewSet, basename='entreprise')

urlpatterns = [
    path('', include(router.urls)),
       # path('entreprises/', EntrepriseListAPIView.as_view(), name='entreprise-list'),
    #path('entreprises/active/', ActiveEntrepriseAPIView.as_view(), name='active-entreprise'),
]
