from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.files.base import ContentFile
from .models import Publication
from .scraping import scrape_the_very_latest_publication
from .decorators import superuser_required
from .tasks import process_publication_pipeline 
import requests
import os
import time

@superuser_required
def scraping_control_view(request):
    """
    Gère le panneau de contrôle du scraping.
    Affiche la page (GET) et traite la demande de scraping (POST) pour télécharger la publication la plus récente et lancer son traitement asynchrone via Celery.
    """
    context = {
        'recent_publications': Publication.objects.all()[:10]
    }

    if request.method == 'POST':
        messages.info(request, "Vérification de la dernière publication sur dgcmef.gov.bf...")
        
        try:
            latest_pub_data = None
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    latest_pub_data = scrape_the_very_latest_publication()
                    if latest_pub_data:
                        break
                except requests.exceptions.ConnectTimeout:
                    messages.warning(request, f"Tentative {attempt + 1}/{max_retries}: Le serveur ne répond pas. Nouvelle tentative dans 5 secondes...")
                    time.sleep(5)
            
            if not latest_pub_data:
                messages.error(request, "Le site n'a pas répondu après plusieurs tentatives. Il est probablement inaccessible.")
                return redirect('scraping_control')

            if Publication.objects.filter(url=latest_pub_data['url']).exists():
                messages.info(request, "La base de données est déjà à jour. La dernière publication a déjà été téléchargée.")
                return redirect('scraping_control')
            
            try:
                pdf_response = requests.get(latest_pub_data['url'], timeout=60)
                pdf_response.raise_for_status()
                
                pdf_name = os.path.basename(pdf_response.url.split('?')[0])
                
                nouvelle_pub = Publication(
                    title=latest_pub_data['title'],
                    url=latest_pub_data['url'],
                    numero_revue=latest_pub_data['numero_revue'],
                    date_publication=latest_pub_data['date_publication'],
                )
                
                nouvelle_pub.fichier_pdf.save(pdf_name, ContentFile(pdf_response.content), save=True)
                
                # --- Étape 2: Déclencher la tâche Celery ---
                # On passe l'ID de la publication nouvellement créée à la tâche.
                # .delay() exécute la tâche en arrière-plan.
                process_publication_pipeline.delay(nouvelle_pub.id)
                
                # Le message de succès est maintenant différent pour informer l'utilisateur.
                messages.success(request, f"Nouvelle publication '{nouvelle_pub.title}' téléchargée. Le traitement en arrière-plan a été lancé.")

            except requests.RequestException as e:
                messages.error(request, f"Erreur de téléchargement pour {latest_pub_data['title']}: {e}")

        except Exception as e:
            messages.error(request, f"Une erreur critique est survenue durant le scraping : {e}")
        
        return redirect('scraping_control')

    return render(request, 'veille_marches/scraping_control.html', context)


from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from .models import Notification
from .serializers import NotificationSerializer, NotificationListSerializer, NotificationUpdateSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les notifications
    """
    queryset = Notification.objects.select_related(
        'entreprise', 'domaine', 'marche', 'lot'
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_notification', 'lu', 'entreprise', 'domaine']
    search_fields = ['marche__objet', 'entreprise__nom', 'domaine__nom']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NotificationListSerializer
        elif self.action in ['update', 'partial_update']:
            return NotificationUpdateSerializer
        return NotificationSerializer
    
    def get_queryset(self):
        """Filtrage par entreprise si spécifié"""
        queryset = super().get_queryset()
        entreprise_id = self.request.query_params.get('entreprise_id')
        
        if entreprise_id:
            queryset = queryset.filter(entreprise_id=entreprise_id)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Marquer toutes les notifications comme lues pour une entreprise"""
        entreprise_id = request.data.get('entreprise_id')
        
        if not entreprise_id:
            return Response(
                {'error': 'entreprise_id requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = Notification.objects.filter(
            entreprise_id=entreprise_id,
            lu=False
        ).update(lu=True)
        
        return Response({
            'message': f'{updated_count} notifications marquées comme lues'
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des notifications pour une entreprise"""
        entreprise_id = request.query_params.get('entreprise_id')
        
        if not entreprise_id:
            return Response(
                {'error': 'entreprise_id requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = Notification.objects.filter(entreprise_id=entreprise_id)
        
        stats = {
            'total': queryset.count(),
            'non_lues': queryset.filter(lu=False).count(),
            'par_type': queryset.values('type_notification').annotate(
                count=Count('id')
            ),
            'par_domaine': queryset.filter(
                type_notification='DOMAINE'
            ).values('domaine__nom').annotate(
                count=Count('id')
            )[:10]  # Top 10 domaines
        }
        
        return Response(stats)
    
    @action(detail=True, methods=['post'])
    def toggle_read(self, request, pk=None):
        """Basculer le statut lu/non lu d'une notification"""
        notification = self.get_object()
        notification.lu = not notification.lu
        notification.save()
        
        return Response({
            'id': notification.id,
            'lu': notification.lu
        })
