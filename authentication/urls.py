from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from . import views
urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # pour obtenir token
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # pour rafraîchir token
    path('register/', views.RegisterView.as_view(), name='register'),
    path('me/', views.UserDetailView.as_view(), name='user-detail'),
]
