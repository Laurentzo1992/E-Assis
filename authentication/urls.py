from django.urls import path
from .views import RegisterView, LoginView, ProfileView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views
urlpatterns = [
        path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),

    path('profile/', ProfileView.as_view(), name='profile'),
       # path('api/password_reset/', include('django_rest_passwordreset.urls', namespace='password_reset')),
]
