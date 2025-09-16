from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from gestion_caisses.models import RapportActivite, Caisse
from datetime import datetime, timedelta
import random
from django.db.models import Count


class Command(BaseCommand):
    help = 'Crée des rapports d\'activités de test pour alimenter la base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--nombre',
            type=int,
            default=20,
            help='Nombre de rapports à créer (défaut: 20)'
        )
        parser.add_argument(
            '--caisses',
            action='store_true',
            help='Créer des rapports spécifiques aux caisses existantes'
        )

    def handle(self, *args, **options):
        nombre_rapports = options['nombre']
        utiliser_caisses = options['caisses']
        
        # Récupérer les utilisateurs et caisses existants
        users = list(User.objects.filter(is_staff=True))
        caisses = list(Caisse.objects.all())
        
        if not users:
            self.stdout.write(
                self.style.ERROR('Aucun utilisateur staff trouvé. Créez d\'abord des utilisateurs.')
            )
            return
        
        if utiliser_caisses and not caisses:
            self.stdout.write(
                self.style.ERROR('Aucune caisse trouvée. Créez d\'abord des caisses.')
            )
            return
        
        # Types de rapports disponibles
        types_rapports = ['general', 'financier', 'prets', 'membres', 'echeances']
        statuts = ['EN_ATTENTE', 'GENERE', 'ECHEC']
        
        # Périodes de test (6 derniers mois)
        aujourd_hui = timezone.now().date()
        date_debut = aujourd_hui - timedelta(days=180)
        
        rapports_crees = 0
        
        for i in range(nombre_rapports):
            try:
                # Choisir aléatoirement les paramètres
                type_rapport = random.choice(types_rapports)
                statut = random.choice(statuts)
                utilisateur = random.choice(users)
                
                # Choisir une caisse ou laisser vide pour les rapports globaux
                caisse = None
                if utiliser_caisses and caisses and random.choice([True, False]):
                    caisse = random.choice(caisses)
                
                # Générer des dates aléatoires dans la période
                jours_aleatoires = random.randint(0, 180)
                date_creation = date_debut + timedelta(days=jours_aleatoires)
                
                # Pour les rapports générés, ajouter une date de génération
                date_generation = None
                if statut == 'GENERE':
                    date_generation = timezone.now() - timedelta(days=random.randint(0, 30))
                
                # Générer des données JSON simulées pour les rapports générés
                donnees = {}
                if statut == 'GENERE':
                    donnees = self._generer_donnees_simulees(type_rapport, caisse)
                
                # Créer le rapport
                rapport = RapportActivite.objects.create(
                    caisse=caisse,
                    type_rapport=type_rapport,
                    date_debut=date_creation - timedelta(days=random.randint(7, 30)),
                    date_fin=date_creation,
                    statut=statut,
                    genere_par=utilisateur if statut == 'GENERE' else None,
                    date_generation=date_generation,
                    donnees=donnees,
                    notes=self._generer_notes(type_rapport, statut, caisse)
                )
                
                rapports_crees += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Rapport créé: {rapport} (Statut: {statut})'
                    )
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Erreur lors de la création du rapport {i+1}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ {rapports_crees} rapports d\'activités créés avec succès!'
            )
        )
        
        # Afficher des statistiques
        self._afficher_statistiques()

    def _generer_donnees_simulees(self, type_rapport, caisse):
        """Génère des données JSON simulées selon le type de rapport"""
        if type_rapport == 'general':
            return {
                'total_caisses': random.randint(5, 50),
                'total_membres': random.randint(100, 1000),
                'total_prets': random.randint(50, 500),
                'total_fonds': random.randint(1000000, 10000000),
                'periode': '6 derniers mois',
                'generation_date': timezone.now().isoformat()
            }
        elif type_rapport == 'financier':
            return {
                'fonds_disponibles': random.randint(500000, 5000000),
                'fonds_initiaux': random.randint(1000000, 8000000),
                'mouvements_total': random.randint(100, 1000),
                'transferts_total': random.randint(10, 100),
                'devise': 'FCFA',
                'periode': '6 derniers mois',
                'generation_date': timezone.now().isoformat()
            }
        elif type_rapport == 'prets':
            return {
                'prets_en_cours': random.randint(20, 200),
                'prets_rembourses': random.randint(30, 300),
                'prets_en_retard': random.randint(0, 20),
                'montant_total_prets': random.randint(5000000, 50000000),
                'montant_rembourse': random.randint(2000000, 20000000),
                'taux_remboursement': random.uniform(0.6, 0.95),
                'periode': '6 derniers mois',
                'generation_date': timezone.now().isoformat()
            }
        elif type_rapport == 'membres':
            return {
                'total_membres': random.randint(100, 1000),
                'membres_actifs': random.randint(80, 800),
                'membres_nouveaux': random.randint(10, 100),
                'repartition_par_role': {
                    'PRESIDENTE': random.randint(5, 50),
                    'SECRETAIRE': random.randint(5, 50),
                    'TRESORIERE': random.randint(5, 50),
                    'MEMBRE': random.randint(50, 500)
                },
                'periode': '6 derniers mois',
                'generation_date': timezone.now().isoformat()
            }
        elif type_rapport == 'echeances':
            return {
                'total_echeances': random.randint(100, 1000),
                'echeances_payees': random.randint(50, 500),
                'echeances_en_attente': random.randint(30, 300),
                'echeances_en_retard': random.randint(0, 50),
                'montant_total_echeances': random.randint(1000000, 10000000),
                'montant_paye': random.randint(500000, 5000000),
                'periode': '6 derniers mois',
                'generation_date': timezone.now().isoformat()
            }
        
        return {}

    def _generer_notes(self, type_rapport, statut, caisse):
        """Génère des notes appropriées pour le rapport"""
        notes = []
        
        if caisse:
            notes.append(f"Rapport généré pour la caisse: {caisse.nom_association}")
        
        if statut == 'GENERE':
            notes.append("Rapport généré avec succès")
            notes.append(f"Type: {type_rapport}")
            notes.append("Données collectées et formatées")
        elif statut == 'ECHEC':
            notes.append("Erreur lors de la génération")
            notes.append("Vérifier les paramètres et réessayer")
        else:  # EN_ATTENTE
            notes.append("En attente de génération")
            notes.append("Cliquer sur 'Générer le rapport' pour procéder")
        
        return "\n".join(notes)

    def _afficher_statistiques(self):
        """Affiche des statistiques sur les rapports créés"""
        total_rapports = RapportActivite.objects.count()
        rapports_par_type = RapportActivite.objects.values('type_rapport').annotate(
            count=Count('id')
        ).order_by('type_rapport')
        
        rapports_par_statut = RapportActivite.objects.values('statut').annotate(
            count=Count('id')
        ).order_by('statut')
        
        self.stdout.write("\n📊 Statistiques des rapports:")
        self.stdout.write(f"Total des rapports: {total_rapports}")
        
        self.stdout.write("\nPar type:")
        for item in rapports_par_type:
            self.stdout.write(f"  - {item['type_rapport']}: {item['count']}")
        
        self.stdout.write("\nPar statut:")
        for item in rapports_par_statut:
            self.stdout.write(f"  - {item['statut']}: {item['count']}")
