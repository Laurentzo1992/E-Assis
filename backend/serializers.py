from rest_framework import serializers
from .models import (
    Publication, TypeProcedure, Marche, AppelOffre, Resultat, Lot,
    Domaine, PublicationDomaine, Entreprise, Alerte
)
from authentication.models import Utilisateur
from entreprise.models import Entreprise , EntrepriseDomaine , SecteurActivite, EntrepriseSecteur
from entreprise.serializers  import EntrepriseSerializer  ,DomaineSerializer


# Utilisateur
class UtilisateurSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseSerializer(read_only=True)
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'nom', 'prenom', 'entreprise', 'authenifie', 'role']

# Publication
class PublicationSerializer(serializers.ModelSerializer):
    domaines = DomaineSerializer(many=True, read_only=True)
    class Meta:
        model = Publication
        fields = [
            'id', 'titre', 'numero', 'date_publication', 'source',
            'type_publication',  'domaines'
        ]

# TypeProcedure
class TypeProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeProcedure
        fields = ['id', 'libelle']

# Lot
class LotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lot
        fields = ['id', 'marche', 'numero_lot', 'description', 'montant']

# Marche (base)
class MarcheSerializer(serializers.ModelSerializer):
    publication = PublicationSerializer(read_only=True)
    type_procedure = TypeProcedureSerializer(read_only=True)
    lots = LotSerializer(many=True, read_only=True)

    class Meta:
        model = Marche
        fields = [
            'id', 'publication', 'type_procedure', 'ministere', 'region',
            'objet', 'budget_min', 'budget_max', 'lots'
        ]

# AppelOffre (hérite de Marche)
class AppelOffreSerializer(MarcheSerializer):
    class Meta(MarcheSerializer.Meta):
        model = AppelOffre
        fields = MarcheSerializer.Meta.fields + [
            'dateDepot', 'referenceDossier', 'lieuDepot',
            'conditionsParticipation', 'criteresSelection',
            'cautionnement', 'dureeValiditeOffres'
        ]


# Resultat
class ResultatSerializer(serializers.ModelSerializer):
    marche = MarcheSerializer(read_only=True)
    entreprise_attributaire = EntrepriseSerializer(read_only=True)

    class Meta:
        model = Resultat
        fields = [
            'marche', 'date_attribution', 'entreprise_attributaire',
            'montant_attribue', 'reference_decision', 'nombre_offres_recues',
            'delai_execution', 'motif_rejet_autres_offres'
        ]

# PublicationDomaine
class PublicationDomaineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationDomaine
        fields = ['id', 'publication', 'domaine']


# Alerte
class AlerteSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseSerializer(read_only=True)
    publication = PublicationSerializer(read_only=True)

    class Meta:
        model = Alerte
        fields = [
            'id', 'entreprise', 'publication', 'type_alerte',
            'date_alerte', 'contenu_alerte', 'canal_alerte',
          
        ]
