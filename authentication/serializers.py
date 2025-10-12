# authentication/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Utilisateur
from django.utils import timezone
import uuid


# ===============================
# 🔹 Utilisateur - CRUD complet
# ===============================
class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'repnom', 'repprenom', 'is_active', 'is_staff', 'date_joined', 'last_login']
        read_only_fields = ['is_active', 'is_staff', 'date_joined', 'last_login']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = Utilisateur.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            repnom=validated_data.get('repnom', ''),
            repprenom=validated_data.get('repprenom', '')
        )
        return user

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.repnom = validated_data.get('repnom', instance.repnom)
        instance.repprenom = validated_data.get('repprenom', instance.repprenom)
        password = validated_data.get('password')
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# ===============================
# 🔹 Profil utilisateur
# ===============================
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'repnom', 'repprenom', 'telephone', 'notifications_actives']
        read_only_fields = ['id', 'email']

    def update(self, instance, validated_data):
        instance.repnom = validated_data.get('repnom', instance.repnom)
        instance.repprenom = validated_data.get('repprenom', instance.repprenom)
        instance.telephone = validated_data.get('telephone', instance.telephone)
        instance.notifications_actives = validated_data.get('notifications_actives', instance.notifications_actives)
        instance.save()
        return instance


# ===============================
# 🔹 Login
# ===============================
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'),
                                email=email, password=password)
            if not user:
                raise serializers.ValidationError("Impossible de se connecter avec les identifiants fournis.", code='authorization')
        else:
            raise serializers.ValidationError('Doit inclure "email" et "password".', code='authorization')

        attrs['user'] = user
        return attrs


# ===============================
# 🔹 Register (avec règles de sécurité)
# ===============================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = ['email', 'password', 'repnom', 'repprenom']
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        # 1️⃣ Vérifier que l'e-mail n'est pas déjà utilisé
        if Utilisateur.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "Cet e-mail est déjà utilisé."})

        # 2️⃣ Vérifier que le mot de passe est différent de l'email
        if email == password:
            raise serializers.ValidationError({"password": "Le mot de passe ne doit pas être identique à l'adresse e-mail."})

        # 3️⃣ Vérifier la longueur minimale du mot de passe (8 caractères)
        if len(password) < 8:
            raise serializers.ValidationError({"password": "Le mot de passe doit contenir au minimum 8 caractères."})

        return attrs

    def create(self, validated_data):
        user = Utilisateur.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            repnom=validated_data.get('repnom', ''),
            repprenom=validated_data.get('repprenom', '')
        )
        return user


# ===============================
# 🔹 Demande de réinitialisation du mot de passe
# ===============================
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    repnom = serializers.CharField(max_length=255)
    repprenom = serializers.CharField(max_length=255)

    def validate(self, data):
        email = data.get('email')
        repnom = data.get('repnom')
        repprenom = data.get('repprenom')
        try:
            user = Utilisateur.objects.get(email=email, repnom=repnom, repprenom=repprenom)
        except Utilisateur.DoesNotExist:
            raise serializers.ValidationError("Aucun utilisateur trouvé avec ces informations.")
        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.reset_password_token = uuid.uuid4()
        user.reset_password_token_created_at = timezone.now()
        user.save()
        return user


# ===============================
# 🔹 Réinitialisation du mot de passe
# ===============================
class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        if len(data['new_password']) < 8:
            raise serializers.ValidationError("Le mot de passe doit contenir au minimum 8 caractères.")
        return data

    def save(self, user):
        user.set_password(self.validated_data['new_password'])
        user.reset_password_token = None
        user.reset_password_token_created_at = None
        user.save()
        return user
