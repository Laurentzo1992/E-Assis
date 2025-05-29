# entreprise/models.py
from django.db import models

class Domaine(models.Model):
    libelle = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

class SecteurActivite(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

class Entreprise(models.Model):
    nom = models.CharField(max_length=255)
    numero_identification = models.CharField(max_length=100, unique=True)
    siret = models.CharField(max_length=20, unique=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    date_creation = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    repnom = models.CharField( max_length= 255, blank=True ,null= True)
    repprenom = models.CharField( max_length= 255, blank=True )
    domaines = models.ManyToManyField(Domaine, through='EntrepriseDomaine')
    secteurs = models.ManyToManyField(SecteurActivite, through='EntrepriseSecteur')
    rccm = models.CharField(max_length=15 , blank=True , null = True)

class EntrepriseDomaine(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    domaine = models.ForeignKey(Domaine, on_delete=models.CASCADE)

class EntrepriseSecteur(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    secteur = models.ForeignKey(SecteurActivite, on_delete=models.CASCADE)
