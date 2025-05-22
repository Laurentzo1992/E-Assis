from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from entreprise.models import Entreprise

class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('L\'email doit être renseigné')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(email, password, **extra_fields)

class Utilisateur(AbstractUser):
    username = None  # Supprime le champ username
    email = models.EmailField('email address', unique=True)

    entreprise = models.ForeignKey(Entreprise, on_delete=models.SET_NULL, null=True, blank=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    notifications_actives = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    def __str__(self):
        return self.email
