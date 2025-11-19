# entreprise/models.py
from django.db import models
from authentication.models import Utilisateur # Importez votre modèle Utilisateur

class Domaine(models.Model):
    libelle = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.libelle

class SecteurActivite(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nom

class Entreprise(models.Model):
    nom = models.CharField(max_length=255)
    numero_identification = models.CharField(max_length=100, unique=True)
    siret = models.CharField(max_length=20, unique=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    date_creation = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    repnom = models.CharField(max_length=255, blank=True, null=True)
    repprenom = models.CharField(max_length=255, blank=True, null=True) # Ajout de null=True
    domaines = models.ManyToManyField(Domaine, through='EntrepriseDomaine')
    secteurs = models.ManyToManyField(SecteurActivite, through='EntrepriseSecteur')
    rccm = models.CharField(max_length=15, blank=True, null=True)
    owner = models.ForeignKey('authentication.Utilisateur', on_delete=models.CASCADE, related_name='owned_entreprises', null=True) # Ajout du propriétaire

    def __str__(self):
        return self.nom

class EntrepriseDomaine(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    domaine = models.ForeignKey(Domaine, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('entreprise', 'domaine') # Empêche les doublons

class EntrepriseSecteur(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    secteur = models.ForeignKey(SecteurActivite, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('entreprise', 'secteur') # Empêche les doublons
