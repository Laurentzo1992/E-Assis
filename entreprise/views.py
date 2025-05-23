from rest_framework import viewsets, permissions
from .models import Domaine, SecteurActivite, Entreprise
from .serializers import (
    DomaineSerializer, SecteurActiviteSerializer,
    EntrepriseSerializer, EntrepriseCreateUpdateSerializer
)

class DomaineViewSet(viewsets.ModelViewSet):
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer
    permission_classes = [permissions.IsAuthenticated]

class SecteurActiviteViewSet(viewsets.ModelViewSet):
    queryset = SecteurActivite.objects.all()
    serializer_class = SecteurActiviteSerializer
    permission_classes = [permissions.IsAuthenticated]

class EntrepriseViewSet(viewsets.ModelViewSet):
    queryset = Entreprise.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return EntrepriseCreateUpdateSerializer
        return EntrepriseSerializer
