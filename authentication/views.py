from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from .serializers import RegisterSerializer, LoginSerializer, ProfileSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.password_validation import validate_password
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from google.oauth2 import id_token
from google.auth.transport import requests
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response('Utilisateur créé avec succès', examples={
                "application/json": {"message": "Utilisateur créé avec succès"}
            }),
            400: 'Erreurs de validation'
        },
        operation_description="Inscription d'un nouvel utilisateur"
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Utilisateur créé avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response('Connexion réussie', examples={
                "application/json": {
                    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                }
            }),
            400: 'Erreurs de validation'
        },
        operation_description="Connexion utilisateur avec JWT"
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: openapi.Response('Déconnexion réussie', examples={
                "application/json": {"message": "Déconnexion réussie"}
            }),
            400: 'Token non trouvé'
        },
        operation_description="Déconnexion utilisateur"
    )
    def post(self, request):
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
            return Response({'message': 'Déconnexion réussie'}, status=status.HTTP_200_OK)
        except Token.DoesNotExist:
            return Response({'error': 'Token non trouvé'}, status=status.HTTP_400_BAD_REQUEST)
        
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'old_password': openapi.Schema(type=openapi.TYPE_STRING, description='Ancien mot de passe'),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, description='Nouveau mot de passe'),
            },
            required=['old_password', 'new_password']
        ),
        responses={
            200: openapi.Response('Mot de passe changé avec succès', examples={
                "application/json": {"message": "Mot de passe changé avec succès"}
            }),
            400: 'Erreurs de validation'
        },
        operation_description="Changement de mot de passe utilisateur"
    )
    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not user.check_password(old_password):
            return Response({'old_password': 'Mot de passe actuel incorrect'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user)
        except Exception as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Mot de passe changé avec succès'}, status=status.HTTP_200_OK)        

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        responses={200: ProfileSerializer},
        operation_description="Récupération du profil utilisateur"
    )
    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

class GoogleLoginAPIView(APIView):
    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token Google requis'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Vérification du token Google
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)
            if not idinfo.get('email_verified'):
                return Response({'error': 'Email non vérifié par Google'}, status=status.HTTP_400_BAD_REQUEST)

            email = idinfo.get('email')
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')

            user, created = User.objects.get_or_create(email=email, defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
                'is_email_verified': False,  # initialement faux
            })

            if created:
                # Envoyer email de confirmation
                self.send_verification_email(user, request)

            if not user.is_email_verified:
                return Response({'detail': 'Veuillez vérifier votre email. Un email de confirmation vous a été envoyé.'}, status=403)

            # Générer tokens JWT
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            })

        except ValueError:
            return Response({'error': 'Token Google invalide'}, status=status.HTTP_400_BAD_REQUEST)

    def send_verification_email(self, user, request):
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.contrib.auth.tokens import default_token_generator

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verification_link = request.build_absolute_uri(
            reverse('verify-email', kwargs={'uidb64': uid, 'token': token})
        )
        subject = 'Confirmez votre adresse email'
        message = f'Bonjour {user.first_name},\n\nMerci de confirmer votre adresse email en cliquant sur ce lien : {verification_link}'
        send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])
        
        
class VerifyEmailAPIView(APIView):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user and default_token_generator.check_token(user, token):
            user.is_email_verified = True
            user.save()
            return Response({'detail': 'Email vérifié avec succès.'})
        else:
            return Response({'error': 'Lien de vérification invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)        