from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import (
    Region, Prefecture, Commune, Canton, Village,
    Caisse, Membre, Pret
)


class ModelTestCase(TestCase):
    """Tests pour les modèles de base"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        # Créer une région
        self.region = Region.objects.create(
            nom='Région des Plateaux',
            code='PLT'
        )
        
        # Créer une préfecture
        self.prefecture = Prefecture.objects.create(
            nom='Préfecture d\'Ogou',
            code='OGO',
            region=self.region
        )
        
        # Créer une commune
        self.commune = Commune.objects.create(
            nom='Commune d\'Atakpamé',
            code='ATA',
            prefecture=self.prefecture
        )
        
        # Créer un canton
        self.canton = Canton.objects.create(
            nom='Canton d\'Atakpamé',
            code='ATA',
            commune=self.commune
        )
        
        # Créer un village
        self.village = Village.objects.create(
            nom='Village d\'Atakpamé Centre',
            code='ATC',
            canton=self.canton
        )
    
    def test_region_creation(self):
        """Test de création d'une région"""
        self.assertEqual(self.region.nom, 'Région des Plateaux')
        self.assertEqual(self.region.code, 'PLT')
        self.assertEqual(str(self.region), 'Région des Plateaux')
    
    def test_prefecture_creation(self):
        """Test de création d'une préfecture"""
        self.assertEqual(self.prefecture.nom, 'Préfecture d\'Ogou')
        self.assertEqual(self.prefecture.region, self.region)
        self.assertEqual(str(self.prefecture), 'Préfecture d\'Ogou (Région des Plateaux)')
    
    def test_commune_creation(self):
        """Test de création d'une commune"""
        self.assertEqual(self.commune.nom, 'Commune d\'Atakpamé')
        self.assertEqual(self.commune.prefecture, self.prefecture)
        self.assertEqual(str(self.commune), 'Commune d\'Atakpamé (Préfecture d\'Ogou)')
    
    def test_canton_creation(self):
        """Test de création d'un canton"""
        self.assertEqual(self.canton.nom, 'Canton d\'Atakpamé')
        self.assertEqual(self.canton.commune, self.commune)
        self.assertEqual(str(self.canton), 'Canton d\'Atakpamé (Commune d\'Atakpamé)')
    
    def test_village_creation(self):
        """Test de création d'un village"""
        self.assertEqual(self.village.nom, 'Village d\'Atakpamé Centre')
        self.assertEqual(self.village.canton, self.canton)
        self.assertEqual(str(self.village), 'Village d\'Atakpamé Centre (Canton d\'Atakpamé)')


class CaisseTestCase(TestCase):
    """Tests pour le modèle Caisse"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        # Créer la hiérarchie territoriale
        self.region = Region.objects.create(nom='Région Test', code='TST')
        self.prefecture = Prefecture.objects.create(
            nom='Préfecture Test', code='TST', region=self.region
        )
        self.commune = Commune.objects.create(
            nom='Commune Test', code='TST', prefecture=self.prefecture
        )
        self.canton = Canton.objects.create(
            nom='Canton Test', code='TST', commune=self.commune
        )
        self.village = Village.objects.create(
            nom='Village Test', code='TST', canton=self.canton
        )
        
        # Créer une caisse
        self.caisse = Caisse.objects.create(
            nom_association='Association Test',
            region=self.region,
            prefecture=self.prefecture,
            commune=self.commune,
            canton=self.canton,
            village=self.village,
            fond_initial=100000,
            statut='ACTIVE'
        )
    
    def test_caisse_creation(self):
        """Test de création d'une caisse"""
        self.assertEqual(self.caisse.nom_association, 'Association Test')
        self.assertEqual(self.caisse.fond_initial, 100000)
        self.assertEqual(self.caisse.statut, 'ACTIVE')
        self.assertIsNotNone(self.caisse.code)
        self.assertTrue(self.caisse.code.startswith('FKMCK'))
    
    def test_caisse_code_generation(self):
        """Test de génération automatique du code"""
        # Créer une deuxième caisse dans la même commune
        caisse2 = Caisse.objects.create(
            nom_association='Association Test 2',
            region=self.region,
            prefecture=self.prefecture,
            commune=self.commune,
            canton=self.canton,
            village=self.village,
            fond_initial=50000,
            statut='ACTIVE'
        )
        
        self.assertNotEqual(self.caisse.code, caisse2.code)
        self.assertTrue(caisse2.code.startswith('FKMCK'))
    
    def test_caisse_properties(self):
        """Test des propriétés calculées"""
        self.assertEqual(self.caisse.nombre_membres, 0)
        self.assertEqual(self.caisse.nombre_prets_actifs, 0)
        self.assertEqual(self.caisse.solde_disponible, 100000)


class MembreTestCase(TestCase):
    """Tests pour le modèle Membre"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        # Créer la hiérarchie territoriale
        self.region = Region.objects.create(nom='Région Test', code='TST')
        self.prefecture = Prefecture.objects.create(
            nom='Préfecture Test', code='TST', region=self.region
        )
        self.commune = Commune.objects.create(
            nom='Commune Test', code='TST', prefecture=self.prefecture
        )
        self.canton = Canton.objects.create(
            nom='Canton Test', code='TST', commune=self.commune
        )
        self.village = Village.objects.create(
            nom='Village Test', code='TST', canton=self.canton
        )
        
        # Créer une caisse
        self.caisse = Caisse.objects.create(
            nom_association='Association Test',
            region=self.region,
            prefecture=self.prefecture,
            commune=self.commune,
            canton=self.canton,
            village=self.village,
            fond_initial=100000,
            statut='ACTIVE'
        )
        
        # Créer un membre
        self.membre = Membre.objects.create(
            numero_carte_electeur='123456789',
            nom='Doe',
            prenoms='Jane',
            date_naissance='1990-01-01',
            adresse='123 Rue Test',
            numero_telephone='+22812345678',
            role='MEMBRE',
            statut='ACTIF',
            caisse=self.caisse
        )
    
    def test_membre_creation(self):
        """Test de création d'un membre"""
        self.assertEqual(self.membre.nom, 'Doe')
        self.assertEqual(self.membre.prenoms, 'Jane')
        self.assertEqual(self.membre.numero_carte_electeur, '123456789')
        self.assertEqual(self.membre.role, 'MEMBRE')
        self.assertEqual(self.membre.statut, 'ACTIF')
        self.assertEqual(self.membre.caisse, self.caisse)
    
    def test_membre_nom_complet(self):
        """Test de la propriété nom_complet"""
        self.assertEqual(self.membre.nom_complet, 'Doe Jane')
    
    def test_membre_validation_30_max(self):
        """Test de la limite de 30 membres par caisse"""
        # Créer 29 membres supplémentaires (total 30)
        for i in range(29):
            Membre.objects.create(
                numero_carte_electeur=f'12345678{i}',
                nom=f'Test{i}',
                prenoms=f'User{i}',
                date_naissance='1990-01-01',
                adresse=f'{i} Rue Test',
                numero_telephone=f'+2281234567{i}',
                role='MEMBRE',
                statut='ACTIF',
                caisse=self.caisse
            )
        
        # Vérifier qu'on a 30 membres
        self.assertEqual(self.caisse.membres.filter(statut='ACTIF').count(), 30)
        
        # Essayer de créer un 31ème membre devrait échouer
        with self.assertRaises(Exception):
            Membre.objects.create(
                numero_carte_electeur='999999999',
                nom='Test31',
                prenoms='User31',
                date_naissance='1990-01-01',
                adresse='999 Rue Test',
                numero_telephone='+22899999999',
                role='MEMBRE',
                statut='ACTIF',
                caisse=self.caisse
            )


class APITestCase(APITestCase):
    """Tests pour l'API REST"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        # Créer un utilisateur de test
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Créer la hiérarchie territoriale
        self.region = Region.objects.create(nom='Région Test', code='TST')
        self.prefecture = Prefecture.objects.create(
            nom='Préfecture Test', code='TST', region=self.region
        )
        self.commune = Commune.objects.create(
            nom='Commune Test', code='TST', prefecture=self.prefecture
        )
        self.canton = Canton.objects.create(
            nom='Canton Test', code='TST', commune=self.commune
        )
        self.village = Village.objects.create(
            nom='Village Test', code='TST', canton=self.canton
        )
        
        # Créer une caisse
        self.caisse = Caisse.objects.create(
            nom_association='Association Test',
            region=self.region,
            prefecture=self.prefecture,
            commune=self.commune,
            canton=self.canton,
            village=self.village,
            fond_initial=100000,
            statut='ACTIVE'
        )
        
        # Authentifier l'utilisateur
        self.client.force_authenticate(user=self.user)
    
    def test_regions_list(self):
        """Test de la liste des régions"""
        url = reverse('gestion_caisses:region-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['nom'], 'Région Test')
    
    def test_prefectures_list(self):
        """Test de la liste des préfectures"""
        url = reverse('gestion_caisses:prefecture-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['nom'], 'Préfecture Test')
    
    def test_caisses_list(self):
        """Test de la liste des caisses"""
        url = reverse('gestion_caisses:caisse-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['nom_association'], 'Association Test')
    
    def test_caisse_detail(self):
        """Test du détail d'une caisse"""
        url = reverse('gestion_caisses:caisse-detail', args=[self.caisse.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nom_association'], 'Association Test')
        self.assertEqual(response.data['code'], self.caisse.code)
    
    def test_dashboard_stats(self):
        """Test des statistiques du tableau de bord"""
        url = reverse('gestion_caisses:dashboard-stats')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_caisses'], 1)
        self.assertEqual(response.data['total_membres'], 0)
        self.assertEqual(response.data['total_prets_actifs'], 0)


class AdminTestCase(TestCase):
    """Tests pour l'interface d'administration"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        # Créer un super utilisateur
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        
        # Créer un client
        self.client = Client()
        
        # Créer la hiérarchie territoriale
        self.region = Region.objects.create(nom='Région Test', code='TST')
        self.prefecture = Prefecture.objects.create(
            nom='Préfecture Test', code='TST', region=self.region
        )
        self.commune = Commune.objects.create(
            nom='Commune Test', code='TST', prefecture=self.prefecture
        )
        self.canton = Canton.objects.create(
            nom='Canton Test', code='TST', commune=self.commune
        )
        self.village = Village.objects.create(
            nom='Village Test', code='TST', canton=self.canton
        )
    
    def test_admin_login(self):
        """Test de connexion à l'admin"""
        # Se connecter
        response = self.client.post('/admin/login/', {
            'username': 'admin',
            'password': 'admin123'
        })
        self.assertEqual(response.status_code, 302)  # Redirection après connexion
        
        # Accéder à la page d'index de l'admin
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestion des Caisses de Femmes')
    
    def test_admin_regions(self):
        """Test de l'accès aux régions dans l'admin"""
        # Se connecter
        self.client.login(username='admin', password='admin123')
        
        # Accéder à la liste des régions
        response = self.client.get('/admin/gestion_caisses/region/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Région Test')
    
    def test_admin_prefectures(self):
        """Test de l'accès aux préfectures dans l'admin"""
        # Se connecter
        self.client.login(username='admin', password='admin123')
        
        # Accéder à la liste des préfectures
        response = self.client.get('/admin/gestion_caisses/prefecture/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Préfecture Test')
