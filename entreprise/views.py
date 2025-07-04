from rest_framework import viewsets, permissions
from .models import Domaine, SecteurActivite, Entreprise
from .serializers import (
    DomaineSerializer, SecteurActiviteSerializer,
    EntrepriseSerializer, EntrepriseCreateUpdateSerializer
)
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny , IsAuthenticated
class DomaineViewSet(viewsets.ModelViewSet):
    #permission_classes = [AllowAny]
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer
    permission_classes = [permissions.IsAuthenticated]

class SecteurActiviteViewSet(viewsets.ModelViewSet):
    #permission_classes = [AllowAny]
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

    def get_queryset(self):
        # Limiter la liste aux entreprises liées à l'utilisateur connecté
        return self.request.user.entreprises.all()

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """
        Récupérer l'entreprise active de l'utilisateur
        """
        entreprise = getattr(request.user, 'active_entreprise', None)
        if entreprise:
            serializer = EntrepriseSerializer(entreprise)
            return Response(serializer.data)
        return Response({"detail": "Aucune entreprise active définie."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='active')
    def set_active(self, request):
        """
        Définir l'entreprise active de l'utilisateur
        """
        entreprise_id = request.data.get('entreprise_id')
        if not entreprise_id:
            return Response({"detail": "Le champ 'entreprise_id' est requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entreprise = request.user.entreprises.get(id=entreprise_id)
        except Entreprise.DoesNotExist:
            return Response({"detail": "Entreprise non trouvée ou non liée à l'utilisateur."}, status=status.HTTP_404_NOT_FOUND)

        request.user.active_entreprise = entreprise
        request.user.save()
        serializer = EntrepriseSerializer(entreprise)
        return Response(serializer.data)
class ActiveEntrepriseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        entreprise = request.user.active_entreprise
        if entreprise:
            return Response({"id": entreprise.id, "nom": entreprise.nom})
        return Response({"id": None, "nom": None})

    def post(self, request):
        entreprise_id = request.data.get("entreprise_id")
        if not entreprise_id:
            return Response({"error": "entreprise_id requis"}, status=400)
        try:
            entreprise = request.user.entreprises.get(id=entreprise_id)
            request.user.active_entreprise = entreprise
            request.user.save()
            return Response({"success": True, "id": entreprise.id, "nom": entreprise.nom})
        except Entreprise.DoesNotExist:
            return Response({"error": "Entreprise non trouvée"}, status=404)
