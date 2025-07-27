from django.db import models
import os
from datetime import date

# Fonction pour organiser les fichiers PDF uploadés dans des dossiers par année/mois
def publication_upload_path(instance, filename):
    pub_date = instance.date_publication if instance.date_publication else date.today()
    return os.path.join('publications', str(pub_date.year), f'{pub_date.month:02d}', filename)

class Publication(models.Model):
    STATUS_CHOICES = [
        ('DOWNLOADED', 'Téléchargé'),
        ('OCR_PENDING', 'OCR en attente'),
        ('PROCESSING', 'Traitement en cours'),
        ('COMPLETED', 'Traité avec succès'),
        ('ERROR', 'Erreur de traitement'),
    ]

    title = models.CharField(max_length=255, verbose_name="Titre de la publication")
    url = models.URLField(max_length=500, unique=True, verbose_name="URL source du PDF")
    numero_revue = models.CharField(max_length=50, blank=True, null=True, verbose_name="Numéro de la revue")
    date_publication = models.DateField(verbose_name="Date de publication")
    
    fichier_pdf = models.FileField(upload_to=publication_upload_path, verbose_name="Fichier PDF")
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='DOWNLOADED', 
        verbose_name="Statut du traitement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Publication"
        verbose_name_plural = "Publications"
        ordering = ['-date_publication']

    def __str__(self):
        return f"Revue N°{self.numero_revue} - {self.date_publication.strftime('%d/%m/%Y')}"