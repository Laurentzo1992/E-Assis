from django.contrib import admin
from django.urls import path, include, re_path # Assurez-vous que re_path est importé
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Configuration de Swagger/DRF-YASG
schema_view = get_schema_view(
   openapi.Info(
      title="API VeilleMarchés Pro", # Titre plus descriptif
      default_version='v1',
      description="Documentation de l'API pour l'application VeilleMarchés Pro",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@votreprojet.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,), # Permet l'accès à la documentation sans authentification
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Routes JWT pour l'authentification
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Routes API pour l'authentification (votre app 'authentication')
    path('api/auth/', include('authentication.urls')),
    
    # Routes API pour le backend (votre app 'backend')
    path('api/backend/', include('backend.urls')),
    
    # Routes API pour les entreprises (votre app 'entreprise')
    path('api/entreprise/', include('entreprise.urls')),
    
    # Routes pour django-allauth (si utilisé pour des vues web ou des signaux)
    path('accounts/', include('allauth.urls')),

    # URLs pour Swagger/DRF-YASG
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    path('veille/', include('veille_marches.urls'))

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
