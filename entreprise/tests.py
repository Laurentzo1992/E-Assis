# entreprise/tests.py

from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from .models import Domaine, SecteurActivite, Entreprise

User = get_user_model()

class EntrepriseAPITests(APITestCase):
    def setUp(self):
        # Création d'un utilisateur et token pour l'authentification
        self.user = User.objects.create_user(email='admin@example.com', password='Passw0rd!2025')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # Création de domaines et secteurs
        self.domaine1 = Domaine.objects.create(libelle="Informatique", description="Domaine IT")
        self.domaine2 = Domaine.objects.create(libelle="Marketing", description="Domaine Marketing")
        self.secteur1 = SecteurActivite.objects.create(nom="SaaS", description="Logiciel en cloud")
        self.secteur2 = SecteurActivite.objects.create(nom="E-commerce", description="Vente en ligne")

    def test_crud_and_relations(self):
        # Création d'un domaine
        url_domaine = reverse('domaine-list')
        data_domaine = {"libelle": "Finance", "description": "Secteur financier"}
        response = self.client.post(url_domaine, data_domaine, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Domaine.objects.count(), 3)

        # Liste des secteurs
        url_secteur = reverse('secteur-list')
        response = self.client.get(url_secteur)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Création d'une entreprise avec relations
        url_entreprise = reverse('entreprise-list')
        data_entreprise = {
            "nom": "Tech Corp",
            "numero_identification": "ID123",
            "siret": "12345678900012",
            "domaine_ids": [self.domaine1.id, self.domaine2.id],
            "secteur_ids": [self.secteur1.id]
        }
        response = self.client.post(url_entreprise, data_entreprise, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entreprise_id = response.data['id']
        entreprise = Entreprise.objects.get(id=entreprise_id)
        self.assertEqual(entreprise.domaines.count(), 2)
        self.assertEqual(entreprise.secteurs.count(), 1)

        
        
        # Récupération des détails de l'entreprise
        url_entreprise_detail = reverse('entreprise-detail', args=[entreprise_id])
        response = self.client.get(url_entreprise_detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['domaines']), 2)
        self.assertEqual(response.data['secteurs'][0]['nom'], "SaaS")

        # Validation unicité SIRET
        data_entreprise_dup = {
            "nom": "New Corp",
            "numero_identification": "ID999",
            "siret": "12345678900012"  # SIRET déjà utilisé
        }
        response = self.client.post(url_entreprise, data_entreprise_dup)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('siret', response.data)

        # Mise à jour de l'entreprise (relations)
        data_update = {
            "nom": "Tech Corp Updated",
            "domaine_ids": [self.domaine2.id],
            "secteur_ids": [self.secteur1.id, self.secteur2.id]
        }
        response = self.client.patch(url_entreprise_detail, data_update, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entreprise.refresh_from_db()
        self.assertEqual(entreprise.nom, "Tech Corp Updated")
        self.assertEqual(entreprise.domaines.count(), 1)
        self.assertEqual(entreprise.secteurs.count(), 2)
