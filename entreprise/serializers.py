from rest_framework import serializers
from .models import Entreprise, Domaine, SecteurActivite

class DomaineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domaine
        fields = ['id', 'libelle', 'description']

class SecteurActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecteurActivite
        fields = ['id', 'nom', 'description']

class EntrepriseSerializer(serializers.ModelSerializer):
    domaines = DomaineSerializer(many=True, read_only=True)
    secteurs = SecteurActiviteSerializer(many=True, read_only=True)

    class Meta:
        model = Entreprise
        fields = [
            'id', 'nom', 'numero_identification', 'siret', 'adresse', 'telephone',
            'email', 'date_creation', 'description', 'repnom', 'repprenom', 'domaines', 'secteurs', 'rccm'
        ]
