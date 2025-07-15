# entreprise/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .models import Domaine, SecteurActivite, Entreprise
from .serializers import (
    DomaineSerializer, SecteurActiviteSerializer,
    EntrepriseSerializer, EntrepriseCreateUpdateSerializer
)
from django.db.models import Q # Import pour le filtrage avancé si nécessaire


class DomaineViewSet(viewsets.ModelViewSet):
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer
    permission_classes = [permissions.IsAuthenticated]

class SecteurActiviteViewSet(viewsets.ModelViewSet):

    queryset = SecteurActivite.objects.all()
    serializer_class = SecteurActiviteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        nom = request.data.get('nom', '').strip()
        description = request.data.get('description', '').strip() if 'description' in request.data else ''
        if not nom:
            return Response({"detail": "Le nom du secteur est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)
        if SecteurActivite.objects.filter(nom__iexact=nom).exists():
            return Response({"detail": "Ce secteur existe déjà."}, status=status.HTTP_400_BAD_REQUEST)
        # Si tout est OK, on crée normalement
        secteur = SecteurActivite.objects.create(nom=nom, description=description)
        serializer = SecteurActiviteSerializer(secteur)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class EntrepriseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]


    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return EntrepriseCreateUpdateSerializer
        return EntrepriseSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Récupère l'objet créé et renvoie la version détaillée
        entreprise = Entreprise.objects.get(pk=response.data['id'])
        serializer = EntrepriseSerializer(entreprise)
        return Response(serializer.data, status=response.status_code)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        # Récupère l'objet modifié et renvoie la version détaillée
        entreprise = self.get_object()
        serializer = EntrepriseSerializer(entreprise)
        return Response(serializer.data, status=response.status_code)

    def get_queryset(self):
        # Filtre les entreprises appartenant à l'utilisateur connecté
        # Utilise le related_name 'owned_entreprises' défini dans authentication/models.py
        return self.request.user.owned_entreprises.all()

    def perform_create(self, serializer):
        # Définit automatiquement le propriétaire de l'entreprise comme l'utilisateur actuel
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """
        Récupérer l'entreprise active de l'utilisateur connecté.
        """
        # S'assure que active_entreprise est un ForeignKey sur le modèle Utilisateur
        entreprise = getattr(request.user, 'active_entreprise', None)
        if entreprise:
            serializer = EntrepriseSerializer(entreprise)
            return Response(serializer.data)
        return Response({"detail": "Aucune entreprise active définie."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='set-active') # Renommé url_path pour plus de clarté
    def set_active(self, request):
        """
        Définir l'entreprise active de l'utilisateur.
        Nécessite 'entreprise_id' dans le corps de la requête.
        """
        entreprise_id = request.data.get('entreprise_id')
        if not entreprise_id:
            return Response({"detail": "Le champ 'entreprise_id' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # S'assurer que l'entreprise appartient bien à l'utilisateur
            # Utilise get_queryset() pour filtrer les entreprises accessibles par l'utilisateur
            entreprise = self.get_queryset().get(id=entreprise_id)
        except Entreprise.DoesNotExist:
            return Response({"detail": "Entreprise non trouvée ou non liée à l'utilisateur."}, status=status.HTTP_404_NOT_FOUND)

        request.user.active_entreprise = entreprise
        request.user.save()
        serializer = EntrepriseSerializer(entreprise)
        return Response(serializer.data, status=status.HTTP_200_OK)
