# backend/serializers.py

from rest_framework import serializers
from .models import (
    Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot,
    Domaine, PublicationDomaine, Alerte, Notification
)
from authentication.models import Utilisateur
from entreprise.serializers import EntrepriseSerializer, DomaineSerializer

# --- SERIALIZER POUR LES NOTIFICATIONS ---
class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer ENRICHI pour le modèle Notification.
    Utilise des champs dénormalisés et des champs calculés pour fournir un maximum
    de contexte au frontend en un seul appel API.
    """
    entreprise_nom = serializers.CharField(source='entreprise.nom', read_only=True)
    domaine_libelle = serializers.CharField(source='domaine.libelle', read_only=True, allow_null=True)
    marche_objet = serializers.CharField(source='marche.objet', read_only=True, allow_null=True)
    
    # --- AJOUTS CLÉS ---
    
    # 1. Ajoute les informations de l'appel d'offre si applicable
    marche_date_depot = serializers.DateTimeField(source='marche.appel_offre.date_depot', read_only=True, allow_null=True)
    
    # 2. Ajoute les informations générales du résultat si applicable
    marche_date_attribution = serializers.DateField(source='marche.resultat.date_attribution', read_only=True, allow_null=True)
    
    # 3. CHAMP CALCULÉ : L'information la plus importante pour l'utilisateur !
    resultat_pour_entreprise = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'type_notification', 'lu', 'created_at', 'message',
            'entreprise_nom', 'domaine_libelle', 'marche_objet',
            'marche_date_depot', 'marche_date_attribution',
            'resultat_pour_entreprise',
            'entreprise', 'marche', 'domaine', 'lot'
        ]

    def get_resultat_pour_entreprise(self, obj):
        """
        Cette méthode calcule l'issue du marché pour l'entreprise notifiée.
        `obj` est l'instance de la Notification en cours de sérialisation.
        """
        # On ne calcule ce champ que pour les notifications de type "résultat".
        if obj.type_notification == 'ENTREPRISE_SPECIFIQUE' and obj.marche:
            try:
                # On cherche le lot spécifique où l'entreprise de la notification a participé
                # dans le marché concerné.
                lot_concerne = Lot.objects.get(marche=obj.marche, entreprise_concernee=obj.entreprise)
                
                # On retourne un objet structuré avec les informations clés.
                return {
                    'statut': lot_concerne.get_statut_display(), # 'Retenu', 'Rejeté', etc. (plus lisible)
                    'rang': lot_concerne.rang,
                    'montant_propose': lot_concerne.montant_propose,
                    'motif': lot_concerne.motif,
                    'description_lot': lot_concerne.description,
                }
            except Lot.DoesNotExist:
                # L'entreprise a été notifiée mais on ne trouve pas sa participation (cas rare).
                return None
            except Lot.MultipleObjectsReturned:
                lot_concerne = Lot.objects.filter(marche=obj.marche, entreprise_concernee=obj.entreprise).first()
                return {
                    'statut': lot_concerne.get_statut_display(),
                    'rang': lot_concerne.rang,
                    'montant_propose': lot_concerne.montant_propose,
                    'motif': lot_concerne.motif,
                    'description_lot': lot_concerne.description,
                }
        return None
        
class UtilisateurSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseSerializer(read_only=True)
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'nom', 'prenom', 'entreprise', 'authenifie', 'role']

class PublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = ['id', 'title', 'numero_revue', 'date_publication', 'url']

class TypeProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProcedure
        fields = ['id', 'libelle']

class LotSerializer(serializers.ModelSerializer):
    # Ajout du nom de l'entreprise pour un affichage facile
    nom_entreprise_texte = serializers.CharField(read_only=True)

    class Meta:
        model = Lot
        fields = [
            'id', 'marche', 'numero_lot', 'description', 'montant_propose',
            'statut', 'rang', 'motif', 'nom_entreprise_texte'
        ]

class MarcheSerializer(serializers.ModelSerializer):
    publication = PublicationSerializer(read_only=True)
    type_procedure = TypeProcedureSerializer(read_only=True)
    # 'lots' sera optimisé par prefetch_related dans la vue.
    lots = LotSerializer(many=True, read_only=True)

    class Meta:
        model = Marche
        fields = [
            'id', 'publication', 'type_procedure', 'ministere', 'region',
            'objet', 'budget_min', 'budget_max', 'lots'
        ]

class AppelOffreSerializer(serializers.ModelSerializer):
    marche = MarcheSerializer(read_only=True)

    class Meta:
        model = AppelOffre
        fields = [
            'marche',  # Contient toutes les infos du marché
            'date_depot', 'reference_dossier', 'lieu_depot',
            'cautionnement', 'duree_validite_offres'
        ]

class ResultatSerializer(serializers.ModelSerializer):
    marche = MarcheSerializer(read_only=True)
    class Meta:
        model = Resultat
        fields = [
            'marche', 'date_attribution',
            'reference_decision', 'nombre_offres_recues',
            'delai_execution'
        ]

class PublicationDomaineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationDomaine
        fields = ['id', 'publication', 'domaine']

class AlerteSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseSerializer(read_only=True)
    publication = PublicationSerializer(read_only=True)

    class Meta:
        model = Alerte
        fields = [
            'id', 'entreprise', 'publication', 'type_alerte',
            'date_alerte', 'contenu_alerte', 'canal_alerte',
        ]