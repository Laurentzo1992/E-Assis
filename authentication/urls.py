# authentication/urls.py
from django.urls import path, include
# Correction: Importez EmailVerifyView
from .views import RegisterView, LoginView, ProfileView, GoogleLoginAPIView, EmailVerifyView, ChangePasswordView, ResetPasswordRequestView, ResetPasswordConfirmView, activate_account

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('google-login/', GoogleLoginAPIView.as_view(), name='google_login'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('reset-password-request/', ResetPasswordRequestView.as_view(), name='reset_password_request'),
    path('reset-password-confirm/', ResetPasswordConfirmView.as_view(), name='reset_password_confirm'),
    # RÉTABLI : Route pour la vérification d'email
    path('verify-email/<str:uidb64>/<str:token>/', EmailVerifyView.as_view(), name='email_verify'),
    path('activate/<uuid:token>/', activate_account, name='activate-account'),
]
