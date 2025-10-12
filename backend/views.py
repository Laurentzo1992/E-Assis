# /backend/views.py

from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot,
    Domaine, PublicationDomaine, Alerte, Notification
)
from .serializers import (
    PublicationSerializer, TypeProcedureSerializer, MarcheSerializer,
    AppelOffreSerializer, ResultatSerializer, LotSerializer,
    DomaineSerializer, PublicationDomaineSerializer, AlerteSerializer,
    NotificationSerializer
)

# --- VIEWSET POUR LES NOTIFICATIONS---
class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet ENRICHI pour lister, filtrer et mettre à jour (marquer comme lu)
    les notifications d'un utilisateur.
    Hérite de ModelViewSet pour autoriser les requêtes PATCH.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    # --- FILTRES AMÉLIORÉS ---
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = {
        'type_notification': ['exact'], # Pour ?type_notification=DOMAINE
        'lu': ['exact'],                # Pour ?lu=false
        'created_at': ['gte', 'lte'],   # Pour le filtre par date
        'entreprise': ['exact'],
    }
    
    search_fields = ['marche__objet', 'message'] # Recherche dans l'objet du marché ou le message
    ordering_fields = ['created_at']
    ordering = ['-created_at'] # Tri par défaut

    def get_queryset(self):
        """
        Surcharge du queryset pour garantir la sécurité et la performance.
        Un utilisateur ne voit QUE les notifications des entreprises qu'il possède.
        """
        user_entreprises = self.request.user.owned_entreprises.all()
        queryset = Notification.objects.filter(entreprise__in=user_entreprises)
        
        return queryset.select_related(
            'entreprise', 'marche', 'domaine', 'lot'
        )

class PublicationViewSet(viewsets.ModelViewSet):
    queryset = Publication.objects.all().order_by('-date_publication')
    serializer_class = PublicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'date_publication': ['gte', 'lte'],
        'publicationdomaine__domaine': ['exact']
    }
    search_fields = ['title', 'numero_revue']
    ordering_fields = ['date_publication']

class TypeProcedureViewSet(viewsets.ModelViewSet):
    queryset = TypeProcedure.objects.all()
    serializer_class = TypeProcedureSerializer
    permission_classes = [IsAdminUser]

class MarcheViewSet(viewsets.ModelViewSet):
    queryset = Marche.objects.select_related('publication', 'type_procedure').prefetch_related('lots').all()
    serializer_class = MarcheSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['region', 'type_procedure']
    search_fields = ['objet', 'ministere']
    ordering_fields = ['budget_min', 'budget_max']
    
class MarcheDetailViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MarcheSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Marche.objects.select_related(
            'publication', 
            'type_procedure',
            'appel_offre',
            'resultat'
        ).prefetch_related(
            'lots__entreprise_concernee'
        ).all()

class AppelOffreViewSet(viewsets.ModelViewSet):
    queryset = AppelOffre.objects.select_related('marche__publication', 'marche__type_procedure').all()
    serializer_class = AppelOffreSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['marche__region']
    search_fields = ['marche__objet', 'reference_dossier', 'lieu_depot']
    ordering_fields = ['date_depot']

class ResultatViewSet(viewsets.ModelViewSet):
    queryset = Resultat.objects.select_related('marche__publication', 'marche__type_procedure').all()
    serializer_class = ResultatSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['marche__objet']
    ordering_fields = ['date_attribution']

class LotViewSet(viewsets.ModelViewSet):
    queryset = Lot.objects.select_related('marche').all()
    serializer_class = LotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['marche', 'statut']
    search_fields = ['description', 'nom_entreprise_texte']
    ordering_fields = ['numero_lot', 'montant_propose']

class DomaineViewSet(viewsets.ModelViewSet):
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer
    permission_classes = [IsAuthenticated]

class PublicationDomaineViewSet(viewsets.ModelViewSet):
    queryset = PublicationDomaine.objects.all()
    serializer_class = PublicationDomaineSerializer
    permission_classes = [IsAuthenticated]

class AlerteViewSet(viewsets.ModelViewSet):
    serializer_class = AlerteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['entreprise', 'type_alerte', 'canal_alerte']
    search_fields = ['contenu_alerte']
    ordering_fields = ['date_alerte']

    def get_queryset(self):
        return Alerte.objects.select_related('entreprise', 'publication').filter(entreprise__user=self.request.user)