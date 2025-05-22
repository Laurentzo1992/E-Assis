from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.urls import reverse

User = get_user_model()

class AuthAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@example.com', password='Passw0rd!2025')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_profile_access(self):
        url = reverse('profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], self.user.email)

    def test_login(self):
        url = reverse('login')
        data = {'email': 'test@example.com', 'password': 'Passw0rd!2025'}
        client = APIClient()
        response = client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        
