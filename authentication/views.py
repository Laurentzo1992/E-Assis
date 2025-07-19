# authentication/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from .serializers import RegisterSerializer, LoginSerializer, ProfileSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError # Importer la validation de Django
from rest_framework.authtoken.models import Token # Si vous utilisez TokenAuthentication
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from google.oauth2 import id_token
from google.auth.transport import requests
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Utilisateur
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes


User = get_user_model()

@api_view(['GET'])
@permission_classes([AllowAny])
def activate_account(request, token):
    print("=== [DEBUG] Tentative d'activation avec le token:", token)

    try:
        user = Utilisateur.objects.get(activation_token=token)
        if user.is_active:
            print("=== [DEBUG] Compte activé:", user.email)
            return Response(
                {"message": "Compte activé."},
                status=status.HTTP_200_OK
            )

        delta = timezone.now() - user.activation_token_created_at
        print("=== [DEBUG] Temps écoulé (s):", delta.total_seconds())

        if delta.total_seconds() > 15 * 60:
            print("=== [DEBUG] Lien expiré.")
            return Response(
                {"error": "Le lien d'activation a expiré."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Activer le compte
        user.is_active = True
        user.is_email_verified = True
        user.save()
        print("=== [DEBUG] Compte activé pour:", user.email)

        return Response(
            {"message": "Compte activé avec succès."},
            status=status.HTTP_200_OK
        )

    except Utilisateur.DoesNotExist:
        print("=== [DEBUG] Token invalide.")
        return Response(
            {"error": "Lien invalide."},
            status=status.HTTP_400_BAD_REQUEST
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response('Utilisateur créé avec succès'),
            400: 'Erreurs de validation'
        },
        operation_description="Inscription d'un nouvel utilisateur"
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.is_active = False  # L'utilisateur doit activer son compte
            user.save()

            # Création du lien d’activation vers le frontend React
            activation_link = f"{settings.FRONTEND_DOMAIN}/verification/{user.activation_token}"

            # Email HTML
            html_message = render_to_string('emails/activation_email.html', {
                'user': user,
                'activation_link': activation_link
            })
            text_message = strip_tags(html_message)

            # Envoi de l'email
            send_mail(
                'Vérification de votre compte',
                text_message,
                settings.EMAIL_HOST_USER,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )

            return Response(
                {"message": "Utilisateur créé. Vérifiez votre email pour activer votre compte."},
                status=status.HTTP_201_CREATED
            )
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
            # Si la vérification par email est désactivée lors de l'inscription,
            # cette vérification peut être commentée ou supprimée si tous les utilisateurs
            # sont considérés comme vérifiés dès l'inscription.
            # Cependant, si vous avez des utilisateurs existants qui n'ont pas vérifié leur email,
            # ou si la logique de GoogleLoginAPIView est différente, vous pouvez la garder.
            # Pour une désactivation complète de la vérification, commentez la ligne ci-dessous.
            # if not user.is_email_verified:
            #     return Response({"detail": "Veuillez vérifier votre adresse email avant de vous connecter."}, status=status.HTTP_403_FORBIDDEN)
            
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
        # Pour JWT, la déconnexion se fait côté client en invalidant le refresh token.
        # Cette logique est pour révoquer le token du côté serveur (blacklist).
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist() # Ou token.rotate() si vous voulez implémenter le "refresh token rotation"
            return Response({'message': 'Déconnexion réussie'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response({"old_password": ["Ancien mot de passe incorrect."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Mot de passe changé avec succès."}, status=status.HTTP_200_OK)

class ResetPasswordRequestView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description='Email de l\'utilisateur'),
            },
            required=['email']
        ),
        responses={
            200: openapi.Response('Email de réinitialisation envoyé', examples={
                "application/json": {"message": "Un lien de réinitialisation de mot de passe a été envoyé à votre adresse email."}
            }),
            400: 'Email non fourni ou utilisateur non trouvé'
        },
        operation_description="Demande de réinitialisation de mot de passe"
    )
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"detail": "L'email est requis."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            # Générer le token de réinitialisation et l'UID
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Construire l'URL de réinitialisation (doit pointer vers votre frontend)
            reset_url = f"{settings.FRONTEND_DOMAIN}/reset-password-confirm/{uid}/{token}/" # Adaptez ce chemin à votre route React
            
            subject = 'Réinitialisation de votre mot de passe'
            context = {
                'user_name': f"{user.repprenom} {user.repnom}".strip(),
                'reset_link': reset_url,
            }
            html_message = render_to_string('emails/password_reset_email.html', context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
            return Response({"message": "Un lien de réinitialisation de mot de passe a été envoyé à votre adresse email."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            # Ne pas révéler si l'email existe ou non pour des raisons de sécurité
            return Response({"message": "Si votre adresse email est valide, un lien de réinitialisation vous a été envoyé."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Une erreur est survenue: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResetPasswordConfirmView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'uidb64': openapi.Schema(type=openapi.TYPE_STRING, description='UID encodé en base64'),
                'token': openapi.Schema(type=openapi.TYPE_STRING, description='Token de réinitialisation'),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, description='Nouveau mot de passe'),
            },
            required=['uidb64', 'token', 'new_password']
        ),
        responses={
            200: openapi.Response('Mot de passe réinitialisé avec succès', examples={
                "application/json": {"message": "Votre mot de passe a été réinitialisé avec succès."}
            }),
            400: 'Lien invalide ou expiré / Erreurs de validation du mot de passe'
        },
        operation_description="Confirmation de la réinitialisation du mot de passe"
    )
    def post(self, request):
        uidb64 = request.data.get('uidb64')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            try:
                validate_password(new_password, user)
            except DjangoValidationError as e:
                return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.save()
            return Response({"message": "Votre mot de passe a été réinitialisé avec succès."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Le lien de réinitialisation est invalide ou a expiré."}, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: ProfileSerializer(many=False),
            401: 'Non authentifié'
        },
        operation_description="Récupérer le profil de l'utilisateur connecté"
    )
    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=ProfileSerializer,
        responses={
            200: ProfileSerializer(many=False),
            400: 'Erreurs de validation',
            401: 'Non authentifié'
        },
        operation_description="Mettre à jour le profil de l'utilisateur connecté"
    )
    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id_token': openapi.Schema(type=openapi.TYPE_STRING, description='Token d\'ID Google OAuth2'),
            },
            required=['id_token']
        ),
        responses={
            200: openapi.Response('Connexion Google réussie', examples={
                "application/json": {
                    "refresh": "...",
                    "access": "...",
                    "user": {
                        "id": 1,
                        "email": "test@example.com",
                        "repnom": "Doe", # <-- Changé ici
                        "repprenom": "John" # <-- Changé ici
                    }
                }
            }),
            400: 'Token invalide ou erreur de connexion'
        },
        operation_description="Connexion/inscription via Google OAuth2"
    )
    def post(self, request):
        token = request.data.get('id_token')
        if not token:
            return Response({"detail": "ID token manquant."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Spécifiez votre ID client Google
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)

            email = idinfo['email']
            # Utilisez les champs 'given_name' (prénom) et 'family_name' (nom) de Google
            # et mappez-les à vos champs reprenom et repnom
            repprenom = idinfo.get('given_name', '')
            repnom = idinfo.get('family_name', '')

            # Obtenez ou créez l'utilisateur
            user, created = User.objects.get_or_create(email=email, defaults={
                'repnom': repnom,      # <-- Correction ici
                'repprenom': repprenom, # <-- Correction ici
                'is_email_verified': True, # Les emails Google sont déjà vérifiés
                'is_active': True # Activez l'utilisateur directement
            })

            if created:
                # Définir un mot de passe inutilisable pour les utilisateurs créés via OAuth
                user.set_unusable_password()
                user.save()

            # Générer les tokens JWT
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'repnom': user.repnom,      # <-- Correction ici
                    'repprenom': user.repprenom # <-- Correction ici
                }
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response({"detail": "Token Google invalide."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"Une erreur est survenue: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('uidb64', openapi.IN_PATH, description='UID encodé en base64', type=openapi.TYPE_STRING),
            openapi.Parameter('token', openapi.IN_PATH, description='Token de vérification', type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response('Email vérifié avec succès', examples={
                "application/json": {"message": "Votre adresse email a été vérifiée avec succès."}
            }),
            400: 'Lien de vérification invalide ou expiré'
        },
        operation_description="Vérification de l'adresse email"
    )
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.is_email_verified = True
            user.is_active = True # Active l'utilisateur après vérification
            user.save()
            return Response({"message": "Votre adresse email a été vérifiée avec succès. Vous pouvez maintenant vous connecter."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Le lien de vérification est invalide ou a expiré."}, status=status.HTTP_400_BAD_REQUEST)
