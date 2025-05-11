
from django.db import models
from entreprise.models import Domaine, Entreprise


class Publication(models.Model):
    titre = models.CharField(max_length=255)
    numero = models.CharField(max_length=100)
    date_publication = models.DateField()
    source = models.CharField(max_length=255)
    source_url = models.URLField(blank=True, null=True)
    domaines = models.ManyToManyField(Domaine, through='PublicationDomaine')
    type_publicaton = models.CharField(max_length=100, blank = True , null= True )
    #fichier_pdf = models.CharField(max_length=100 , blank= True, null= True)
    #contenu_extrait = models.TextField(blank= True, null= True)

class TypeProcedure(models.Model):
    libelle = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

class Marche(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    type_procedure = models.ForeignKey(TypeProcedure, on_delete=models.SET_NULL, null=True)
    ministere = models.CharField(max_length=255, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    objet = models.TextField()
    budget_min = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    budget_max = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)

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


class Resultat(models.Model):
    marche = models.OneToOneField(Marche, on_delete=models.CASCADE, primary_key=True)
    date_attribution = models.DateField(blank=True, null=True)
    entreprise_attributaire = models.ForeignKey(Entreprise, on_delete=models.SET_NULL, null=True, blank=True)
    montant_attribue = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    reference_decision = models.CharField(max_length=255, blank=True, null=True)
    nombre_offres_recues = models.IntegerField(blank=True, null=True)
    delai_execution = models.CharField(max_length=255, blank=True, null=True)
    motif_rejet_autres_offres = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'resultat'
        verbose_name = 'Résultat d\'attribution'
        verbose_name_plural = 'Résultats d\'attribution'

    def __str__(self):
        return f"Résultat pour marche {self.marche_id}"

class Lot(models.Model):
    marche = models.ForeignKey(Marche, on_delete=models.CASCADE, related_name='lots')
    numero_lot = models.IntegerField()
    description = models.TextField(blank=True, null=True)
    montant = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'lot'
        verbose_name = 'Lot'
        verbose_name_plural = 'Lots'

    def __str__(self):
        return f"Lot {self.numero_lot} - Marche {self.marche_id}"

class Alerte(models.Model):
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='alertes')
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='alertes')
    type_alerte = models.CharField(max_length=50)
    date_alerte = models.DateTimeField()
    contenu_alerte = models.TextField()
    canal_alerte = models.CharField(max_length=30)

    class Meta:
        db_table = 'alerte'
        verbose_name = 'Alerte'
        verbose_name_plural = 'Alertes'

    def __str__(self):
        return f"Alerte {self.type_alerte} à {self.entreprise} le {self.date_alerte}"
class PublicationDomaine(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    domaine = models.ForeignKey(Domaine, on_delete=models.CASCADE)
