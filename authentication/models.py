# authentication/models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
# from entreprise.models import Entreprise # Cette ligne est commentée pour éviter l'importation circulaire

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
        extra_fields.setdefault('is_active', True)
        return self._create_user(email, password, **extra_fields)

class Utilisateur(AbstractUser):
    username = None  # Supprime le champ username par défaut d'AbstractUser
    email = models.EmailField('email address', unique=True)

    # AJOUT CRUCIAL : Définition des champs repnom et repprenom
    repnom = models.CharField(max_length=255, blank=True, null=True)
    repprenom = models.CharField(max_length=255, blank=True, null=True)

    # Le champ entreprise ici semble être pour une relation 1-à-1 ou principale,
    # mais active_entreprise gère le concept d'entreprise active.
    # Si un utilisateur est lié à UNE entreprise principale (par ex. l'entreprise qu'il gère),
    # ce champ est pertinent. Sinon, il pourrait être redondant avec la relation inverse
    # depuis Entreprise (via related_name='utilisateurs' sur Entreprise).
    # Je le laisse tel quel pour l'instant, mais c'est un point à clarifier pour votre logique métier.
    entreprise = models.ForeignKey(
        'entreprise.Entreprise', # Utilisation de la chaîne de caractères pour éviter l'importation circulaire
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='utilisateurs_principaux' # Ajout d'un related_name pour éviter les conflits
    )

    telephone = models.CharField(max_length=50, blank=True, null=True)
    notifications_actives = models.BooleanField(default=True)

    # Champ pour l'entreprise active de l'utilisateur (pour la gestion multi-entreprise)
    active_entreprise = models.ForeignKey(
        'entreprise.Entreprise', # Utilisation de la chaîne de caractères pour éviter l'importation circulaire
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='active_users' # Nom inverse pour accéder aux utilisateurs actifs depuis une entreprise
    )
    is_email_verified = models.BooleanField(default=False) # Cette ligne DOIT être présente

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # Aucun champ requis en plus de l'email et du mot de passe

    objects = UtilisateurManager()

    def __str__(self):
        return self.email
