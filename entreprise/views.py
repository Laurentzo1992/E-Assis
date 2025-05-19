from rest_framework import viewsets
from .models import Entreprise, Domaine, SecteurActivite
from .serializers import EntrepriseSerializer, DomaineSerializer, SecteurActiviteSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly

class DomaineViewSet(viewsets.ModelViewSet):
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class SecteurActiviteViewSet(viewsets.ModelViewSet):
    queryset = SecteurActivite.objects.all()
    serializer_class = SecteurActiviteSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class EntrepriseViewSet(viewsets.ModelViewSet):
    queryset = Entreprise.objects.all()
    serializer_class = EntrepriseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
