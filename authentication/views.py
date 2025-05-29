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
