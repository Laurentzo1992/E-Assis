from django.contrib.auth.models import AbstractUser
from django.db import models
from entreprise.models import Entreprise

class Utilisateur(AbstractUser):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.SET_NULL, null=True, blank=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    notifications_actives = models.BooleanField(default=True)
