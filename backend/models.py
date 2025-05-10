
from django.db import models
from entreprise.models import Domaine, Entreprise


class Publication(models.Model):
    titre = models.CharField(max_length=255)
    numero = models.CharField(max_length=100)
    date_publication = models.DateField()
    source = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    domaines = models.ManyToManyField(Domaine, through='PublicationDomaine')

class TypeProcedure(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

class Marche(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    type_procedure = models.ForeignKey(TypeProcedure, on_delete=models.SET_NULL, null=True)
    reference = models.CharField(max_length=100)
    objet = models.CharField(max_length=255)
    autorite_contractante = models.CharField(max_length=255)
    montant_estime = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    devise = models.CharField(max_length=10, default="XOF")
    date_publication = models.DateField()
    date_limite = models.DateField(blank=True, null=True)
    lieu_execution = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

class AppelOffre(Marche):
    dateDepot = models.DateField(blank=True, null=True)
    referenceDossier = models.CharField(max_length=255, blank=True, null=True)
    lieuDepot = models.TextField(blank=True, null=True)
    conditionsParticipation = models.TextField(blank=True, null=True)
    criteresSelection = models.TextField(blank=True, null=True)
    cautionnement = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    dureeValiditeOffres = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Appel d'Offre"
        verbose_name_plural = "Appels d'Offres"

class Resultat(Marche):
    entreprise_attributaire = models.ForeignKey(Entreprise, on_delete=models.SET_NULL, null=True, blank=True)
    montant_attribue = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    date_attribution = models.DateField(blank=True, null=True)

class Lot(models.Model):
    marche = models.ForeignKey(Marche, on_delete=models.CASCADE)
    numero_lot = models.CharField(max_length=50)
    intitule = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

class Alerte(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    marche = models.ForeignKey(Marche, on_delete=models.CASCADE)
    message = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    lue = models.BooleanField(default=False)

class PublicationDomaine(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    domaine = models.ForeignKey(Domaine, on_delete=models.CASCADE)
