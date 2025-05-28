from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import (
    Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot,
    Domaine, PublicationDomaine,Alerte
)
from .serializers import (
    PublicationSerializer, TypeProcedureSerializer, MarcheSerializer,
    AppelOffreSerializer, ResultatSerializer, LotSerializer,
    DomaineSerializer, PublicationDomaineSerializer
    , AlerteSerializer
)

# Publication
class PublicationViewSet(viewsets.ModelViewSet):
    queryset = Publication.objects.all().order_by('-date_publication')
    serializer_class = PublicationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'numero', 'source']
    ordering_fields = ['date_publication']

# TypeProcedure
class TypeProcedureViewSet(viewsets.ModelViewSet):
    queryset = TypeProcedure.objects.all()
    serializer_class = TypeProcedureSerializer
    permission_classes = [IsAdminUser]

# Marche
class MarcheViewSet(viewsets.ModelViewSet):
    queryset = Marche.objects.all()
    serializer_class = MarcheSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['objet', 'ministere', 'region']
    ordering_fields = ['budget_min', 'budget_max']

# AppelOffre
class AppelOffreViewSet(viewsets.ModelViewSet):
    queryset = AppelOffre.objects.all()
    serializer_class = AppelOffreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['objet', 'reference_dossier', 'lieu_depot']
    ordering_fields = ['date_depot']

# Resultat
class ResultatViewSet(viewsets.ModelViewSet):
    queryset = Resultat.objects.all()
    serializer_class = ResultatSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['marche__objet', 'entreprise_attributaire__nom']
    ordering_fields = ['date_attribution', 'montant_attribue']

# Lot
class LotViewSet(viewsets.ModelViewSet):
    queryset = Lot.objects.all()
    serializer_class = LotSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description']
    ordering_fields = ['numero_lot', 'montant']

# Domaine
class DomaineViewSet(viewsets.ModelViewSet):
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer

# PublicationDomaine
class PublicationDomaineViewSet(viewsets.ModelViewSet):
    queryset = PublicationDomaine.objects.all()
    serializer_class = PublicationDomaineSerializer


# Alerte
class AlerteViewSet(viewsets.ModelViewSet):
    queryset = Alerte.objects.all()
    serializer_class = AlerteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['type_alerte', 'contenu_alerte']
    ordering_fields = ['date_alerte']

