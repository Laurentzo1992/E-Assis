from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    entreprise_nom = serializers.CharField(source='entreprise.nom', read_only=True)
    domaine_libelle = serializers.CharField(source='domaine.libelle', read_only=True)
    marche_objet = serializers.CharField(source='marche.objet', read_only=True)
    lot_description = serializers.CharField(source='lot.description', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'type_notification', 'entreprise', 'entreprise_nom',
            'marche', 'marche_objet', 'domaine', 'domaine_libelle',
            'lot', 'lot_description', 'lu', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class NotificationListSerializer(serializers.ModelSerializer):
    """Serializer optimisé pour les listes"""
    entreprise_nom = serializers.CharField(source='entreprise.nom', read_only=True)
    domaine_libelle = serializers.CharField(source='domaine.libelle', read_only=True)
    marche_objet = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'type_notification', 'entreprise_nom',
            'marche_objet', 'domaine_libelle', 'lu', 'created_at'
        ]
    
    def get_marche_objet(self, obj):
        if obj.marche:
            return obj.marche.objet  # Ne tronque plus le texte
        return None

class NotificationUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour les mises à jour (marquer comme lu/non lu)"""
    class Meta:
        model = Notification
        fields = ['lu']
