from rest_framework import serializers
from .models import Domaine, SecteurActivite, Entreprise, EntrepriseDomaine, EntrepriseSecteur

class DomaineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domaine
        fields = ['id', 'libelle', 'description']

class SecteurActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecteurActivite
        fields = ['id', 'nom', 'description']

class EntrepriseDomaineSerializer(serializers.ModelSerializer):
    domaine = DomaineSerializer(read_only=True)
    domaine_id = serializers.PrimaryKeyRelatedField(queryset=Domaine.objects.all(), source='domaine', write_only=True)

    class Meta:
        model = EntrepriseDomaine
        fields = ['id', 'domaine', 'domaine_id']

class EntrepriseSecteurSerializer(serializers.ModelSerializer):
    secteur = SecteurActiviteSerializer(read_only=True)
    secteur_id = serializers.PrimaryKeyRelatedField(queryset=SecteurActivite.objects.all(), source='secteur', write_only=True)

    class Meta:
        model = EntrepriseSecteur
        fields = ['id', 'secteur', 'secteur_id']

class EntrepriseSerializer(serializers.ModelSerializer):
    domaines = DomaineSerializer(many=True, read_only=True)
    secteurs = SecteurActiviteSerializer(many=True, read_only=True)

    class Meta:
        model = Entreprise
        fields = [
            'id', 'nom', 'numero_identification', 'siret', 'adresse', 'telephone', 'email',
            'date_creation', 'description', 'repnom', 'repprenom', 'rccm',
            'domaines', 'secteurs',
        ]

class EntrepriseCreateUpdateSerializer(serializers.ModelSerializer):
    # Pour créer/modifier et gérer les relations many-to-many via les tables intermédiaires
    domaine_ids = serializers.PrimaryKeyRelatedField(queryset=Domaine.objects.all(), many=True, write_only=True, required=False)
    secteur_ids = serializers.PrimaryKeyRelatedField(queryset=SecteurActivite.objects.all(), many=True, write_only=True, required=False)

    class Meta:
        model = Entreprise
        fields = [
            'nom', 'numero_identification', 'siret', 'adresse', 'telephone', 'email',
            'date_creation', 'description', 'repnom', 'repprenom', 'rccm',
            'domaine_ids', 'secteur_ids',
        ]

    def create(self, validated_data):
        domaine_ids = validated_data.pop('domaine_ids', [])
        secteur_ids = validated_data.pop('secteur_ids', [])
        entreprise = Entreprise.objects.create(**validated_data)
        for domaine in domaine_ids:
            EntrepriseDomaine.objects.create(entreprise=entreprise, domaine=domaine)
        for secteur in secteur_ids:
            EntrepriseSecteur.objects.create(entreprise=entreprise, secteur=secteur)
        return entreprise

    def update(self, instance, validated_data):
        domaine_ids = validated_data.pop('domaine_ids', None)
        secteur_ids = validated_data.pop('secteur_ids', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if domaine_ids is not None:
            EntrepriseDomaine.objects.filter(entreprise=instance).delete()
            for domaine in domaine_ids:
                EntrepriseDomaine.objects.create(entreprise=instance, domaine=domaine)

        if secteur_ids is not None:
            EntrepriseSecteur.objects.filter(entreprise=instance).delete()
            for secteur in secteur_ids:
                EntrepriseSecteur.objects.create(entreprise=instance, secteur=secteur)

        return instance
