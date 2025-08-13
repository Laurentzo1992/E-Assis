from django.db import models
from django.utils.translation import gettext_lazy as _
import os
from datetime import date
from entreprise.models import Entreprise

# --- Modèles pour la gestion des publications entrantes ---

def publication_upload_path(instance, filename):
    """
    Définit un chemin de sauvegarde organisé pour les PDF : media/publications/ANNEE/MOIS/fichier.pdf
    """
    pub_date = instance.date_publication if instance.date_publication else date.today()
    return os.path.join('publications', str(pub_date.year), f'{pub_date.month:02d}', filename)

class Publication(models.Model):
    """
    Représente un fichier PDF de "La revue des marchés publics" téléchargé.
    C'est le point d'entrée de tout le pipeline de traitement.
    """
    class Status(models.TextChoices):
        DOWNLOADED = 'DOWNLOADED', _('Téléchargé')
        PROCESSING = 'PROCESSING', _('Traitement en cours')
        COMPLETED = 'COMPLETED', _('Traité avec succès')
        ERROR = 'ERROR', _('Erreur de traitement')

    title = models.CharField(_("titre de la publication"), max_length=255)
    url = models.URLField(_("URL source du PDF"), max_length=500, unique=True)
    numero_revue = models.CharField(_("numéro de la revue"), max_length=50, blank=True, null=True)
    date_publication = models.DateField(_("date de publication"))
    
    fichier_pdf = models.FileField(_("fichier PDF"), upload_to=publication_upload_path)
    
    status = models.CharField(
        _("statut du traitement"),
        max_length=20, 
        choices=Status.choices, 
        default=Status.DOWNLOADED
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Publication")
        verbose_name_plural = _("Publications")
        ordering = ['-date_publication']

    def __str__(self):
        return f"Revue N°{self.numero_revue or 'N/A'} du {self.date_publication.strftime('%d/%m/%Y')}"


# --- Modèles pour structurer les données extraites des publications ---

class TypeProcedure(models.Model):
    """
    Catégorise les grandes sections du document (ex: 'Résultats provisoires', 'Appel d'offres').
    """
    libelle = models.CharField(_("libellé"), max_length=255, unique=True)

    class Meta:
        verbose_name = _("Type de Procédure")
        verbose_name_plural = _("Types de Procédures")
        ordering = ['libelle']

    def __str__(self):
        return self.libelle

class Marche(models.Model):
    """
    Table centrale contenant les informations communes à tous les marchés.
    C'est le pivot de toutes les données extraites d'une notice.
    """
    publication = models.ForeignKey(
        Publication, 
        on_delete=models.CASCADE, 
        related_name="marches", 
        verbose_name=_("publication source")
    )
    type_procedure = models.ForeignKey(
        TypeProcedure, 
        on_delete=models.PROTECT, 
        verbose_name=_("type de procédure")
    )
    
    ministere = models.CharField(_("ministère ou entité"), max_length=255, blank=True, null=True)
    region = models.CharField(_("région"), max_length=100, blank=True, null=True)
    objet = models.TextField(_("objet du marché"))
    
    budget_min = models.DecimalField(_("budget minimal"), max_digits=15, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(_("budget maximal"), max_digits=15, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Marché")
        verbose_name_plural = _("Marchés")
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.ministere or 'N/A'}] - {self.objet[:80]}"

class AppelOffre(models.Model):
    """
    Stocke les informations spécifiques aux appels d'offres.
    Étend le modèle Marche via une relation One-to-One.
    """
    marche = models.OneToOneField(
        Marche, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name="appel_offre",
        verbose_name=_("marché associé")
    )
    
    date_depot = models.DateTimeField(_("date et heure limite de dépôt"), null=True, blank=True)
    reference_dossier = models.CharField(_("référence du dossier"), max_length=255, blank=True, null=True)
    lieu_depot = models.TextField(_("lieu de dépôt des offres"), blank=True, null=True)
    cautionnement = models.DecimalField(_("montant du cautionnement"), max_digits=15, decimal_places=2, null=True, blank=True)
    duree_validite_offres = models.CharField(_("durée de validité des offres"), max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _("Appel d'Offre")
        verbose_name_plural = _("Appels d'Offres")

    def __str__(self):
        return self.marche.objet[:100]

class Resultat(models.Model):
    """
    Stocke les informations générales relatives à l'attribution d'un marché.
    Étend le modèle Marche via une relation One-to-One.
    """
    marche = models.OneToOneField(
        Marche, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name="resultat",
        verbose_name=_("marché associé")
    )
    
    date_attribution = models.DateField(_("date d'attribution (délibération)"), null=True, blank=True)
    reference_decision = models.CharField(_("référence de la décision"), max_length=255, blank=True, null=True)
    nombre_offres_recues = models.PositiveIntegerField(_("nombre d'offres reçues"), null=True, blank=True)
    delai_execution = models.CharField(_("délai d'exécution"), max_length=255, blank=True, null=True)
    
    class Meta:
        verbose_name = _("Résultat d'attribution")
        verbose_name_plural = _("Résultats d'attributions")

    def __str__(self):
        return self.marche.objet[:100]

class Lot(models.Model):
    """
    Détaille un lot spécifique d'un marché, qu'il soit attribué ou non.
    """
    class Statut(models.TextChoices):
        RETENU = 'RETENU', _('Retenu')
        NON_CONFORME = 'NON_CONFORME', _('Non conforme')
        ANORMALEMENT_BASSE = 'ANORMALEMENT_BASSE', _('Anormalement basse')
        REJETE = 'REJETE', _('Rejeté')
        AUTRE = 'AUTRE', _('Autre')

    marche = models.ForeignKey(
        Marche, 
        on_delete=models.CASCADE, 
        related_name="lots", 
        verbose_name=_("marché parent")
    )
    entreprise_concernee = models.ForeignKey(
        Entreprise,
        on_delete=models.PROTECT,
        related_name="participations_lots",
        verbose_name=_("entreprise concernée"),
        null=True,
        blank=True
    )
    
    numero_lot = models.CharField(_("numéro du lot"), max_length=50, blank=True, null=True)
    description = models.TextField(_("description du lot"), blank=True, null=True)
    montant_propose = models.DecimalField(_("montant proposé/attribué"), max_digits=15, decimal_places=2, null=True, blank=True)
    
    statut = models.CharField(
        _("statut de l'offre"),
        max_length=50,
        choices=Statut.choices,
        blank=True, null=True
    )
    rang = models.CharField(_("rang"), max_length=50, blank=True, null=True)
    motif = models.TextField(_("motif du statut (si non retenu)"), blank=True, null=True)

    nom_entreprise_texte = models.CharField(
        _("nom de l'entreprise (texte brut)"),
        max_length=255,
        help_text="Nom de l'entreprise tel qu'extrait du document, même si elle n'est pas dans notre base de données."
    )

    class Meta:
        verbose_name = _("Lot / Participation")
        verbose_name_plural = _("Lots / Participations")
        ordering = ['marche', 'numero_lot', 'rang']

    def __str__(self):
        return f"Lot {self.numero_lot or 'unique'} - {self.nom_entreprise_texte}"