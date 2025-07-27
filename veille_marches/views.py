from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.files.base import ContentFile
from .models import Publication
from .scraping import scrape_the_very_latest_publication
from .decorators import superuser_required
import requests
import os
import time


@superuser_required  # Sécurise la vue, accès réservé aux super-utilisateurs.
def scraping_control_view(request):
    """
    Gère le panneau de contrôle du scraping.

    Affiche la page (GET) et traite la demande de scraping (POST) pour
    télécharger la publication la plus récente si elle n'est pas déjà
    dans la base de données.
    """
    context = {
        'recent_publications': Publication.objects.all()[:10]
    }

    if request.method == 'POST':
        messages.info(request, "Vérification de la dernière publication sur dgcmef.gov.bf...")
        
        # Le processus complet est encapsulé pour une gestion robuste des erreurs.
        try:
            latest_pub_data = None
            max_retries = 3
            
            # Implémente une logique de tentatives multiples pour gérer les timeouts de connexion.
            for attempt in range(max_retries):
                try:
                    latest_pub_data = scrape_the_very_latest_publication()
                    # Si le scraping réussit, on arrête les tentatives.
                    if latest_pub_data:
                        break
                except requests.exceptions.ConnectTimeout:
                    # En cas de timeout, on informe l'utilisateur et on attend avant de réessayer.
                    messages.warning(request, f"Tentative {attempt + 1}/{max_retries}: Le serveur ne répond pas. Nouvelle tentative dans 5 secondes...")
                    time.sleep(5)
            
            # Après la boucle, si aucune donnée n'a été récupérée, c'est un échec définitif.
            if not latest_pub_data:
                messages.error(request, "Le site n'a pas répondu après plusieurs tentatives. Il est probablement inaccessible.")
                return redirect('scraping_control')

            # --- Logique métier clé : Éviter les doublons ---
            # On vérifie si une publication avec cette URL existe déjà.
            if Publication.objects.filter(url=latest_pub_data['url']).exists():
                messages.info(request, "La base de données est déjà à jour. La dernière publication a déjà été téléchargée.")
                return redirect('scraping_control')
            
            # Si la publication est nouvelle, procéder au téléchargement et à la sauvegarde.
            try:
                # On utilise un timeout plus long pour le téléchargement du fichier, car il peut être volumineux.
                pdf_response = requests.get(latest_pub_data['url'], timeout=60)
                pdf_response.raise_for_status()  # Lève une exception pour les erreurs HTTP (404, 500, etc.)
                
                pdf_name = os.path.basename(pdf_response.url.split('?')[0])
                
                nouvelle_pub = Publication(
                    title=latest_pub_data['title'],
                    url=latest_pub_data['url'],
                    numero_revue=latest_pub_data['numero_revue'],
                    date_publication=latest_pub_data['date_publication'],
                )
                
                # La méthode .save() du FileField gère l'écriture du fichier physique
                # et la sauvegarde de l'instance du modèle en une seule opération.
                nouvelle_pub.fichier_pdf.save(pdf_name, ContentFile(pdf_response.content), save=True)
                
                # --- CORRECTION DE LA FAUTE DE FRAPPE ICI ---
                messages.success(request, f"Nouvelle publication '{nouvelle_pub.title}' téléchargée avec succès !")

            except requests.RequestException as e:
                # Gère spécifiquement les erreurs liées au réseau pendant le téléchargement.
                messages.error(request, f"Erreur de téléchargement pour {latest_pub_data['title']}: {e}")

        except Exception as e:
            # Gère toute autre erreur imprévue durant le processus.
            messages.error(request, f"Une erreur critique est survenue durant le scraping : {e}")
        
        # Le pattern Post/Redirect/Get évite les resoumissions de formulaire au rafraîchissement.
        return redirect('scraping_control')

    return render(request, 'veille_marches/scraping_control.html', context)