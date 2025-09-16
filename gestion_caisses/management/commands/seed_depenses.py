from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from gestion_caisses.models import Caisse, Membre, Depense
from decimal import Decimal
import random
from datetime import date, timedelta
from django.db import models


class Command(BaseCommand):
    help = 'Crée des dépenses d\'exemple pour tester le système'

    def add_arguments(self, parser):
        parser.add_argument(
            '--nombre',
            type=int,
            default=10,
            help='Nombre de dépenses à créer (défaut: 10)'
        )

    def handle(self, *args, **options):
        nombre_depenses = options['nombre']
        
        # Vérifier qu'il y a des caisses et des membres
        if not Caisse.objects.exists():
            self.stdout.write(
                self.style.ERROR('❌ Aucune caisse trouvée. Créez d\'abord des caisses.')
            )
            return
        
        if not Membre.objects.exists():
            self.stdout.write(
                self.style.ERROR('❌ Aucun membre trouvé. Créez d\'abord des membres.')
            )
            return
        
        # Récupérer les caisses et membres existants
        caisses = list(Caisse.objects.all())
        membres = list(Membre.objects.all())
        
        # Catégories de dépenses
        categories = ['SOLIDARITE', 'PENALITE', 'AUTRE']
        
        # Statuts possibles
        statuts = ['EN_COURS', 'APPROUVEE', 'REJETEE', 'TERMINEE']
        
        # Descriptions d'exemple
        descriptions_solidarite = [
            "Aide médicale pour membre malade",
            "Soutien financier famille en difficulté",
            "Achat de médicaments pour membre",
            "Transport pour consultation médicale",
            "Aide alimentaire d'urgence"
        ]
        
        descriptions_penalite = [
            "Pénalité retard remboursement prêt",
            "Amende pour absence aux réunions",
            "Pénalité pour non-respect des règles",
            "Sanction pour retard de cotisation"
        ]
        
        descriptions_autre = [
            "Achat de matériel de bureau",
            "Frais de transport pour réunion",
            "Achat de fournitures",
            "Frais de communication",
            "Maintenance équipements"
        ]
        
        depenses_crees = 0
        
        for i in range(nombre_depenses):
            # Sélectionner aléatoirement une caisse et un membre
            caisse = random.choice(caisses)
            responsable = random.choice([m for m in membres if m.caisse == caisse])
            
            # Sélectionner une catégorie
            categorie = random.choice(categories)
            
            # Générer une description appropriée
            if categorie == 'SOLIDARITE':
                description = random.choice(descriptions_solidarite)
            elif categorie == 'PENALITE':
                description = random.choice(descriptions_penalite)
            else:
                description = random.choice(descriptions_autre)
            
            # Générer un montant réaliste
            if categorie == 'SOLIDARITE':
                montant = random.choice([5000, 10000, 15000, 20000, 25000])
            elif categorie == 'PENALITE':
                montant = random.choice([1000, 2000, 3000, 5000])
            else:
                montant = random.choice([2000, 5000, 8000, 12000, 15000])
            
            # Générer une date aléatoire dans les 6 derniers mois
            jours_aleatoires = random.randint(0, 180)
            date_depense = date.today() - timedelta(days=jours_aleatoires)
            
            # Sélectionner un statut (plus de probabilité pour EN_COURS et APPROUVEE)
            statut = random.choices(
                statuts, 
                weights=[0.4, 0.4, 0.1, 0.1]
            )[0]
            
            # Créer la dépense
            depense = Depense.objects.create(
                caisse=caisse,
                categorie=categorie,
                montant=Decimal(montant),
                description=description,
                justificatif=f"Justificatif pour {description.lower()}",
                date_depense=date_depense,
                responsable=responsable,
                statut=statut
            )
            
            # Si la dépense est approuvée, ajouter des notes d'approbation
            if statut == 'APPROUVEE':
                depense.notes_approbation = "Dépense approuvée par le comité de gestion"
                depense.save()
            
            depenses_crees += 1
            
            self.stdout.write(
                f"✅ Dépense créée: {depense.caisse.nom_association} - "
                f"{depense.montant} FCFA ({depense.get_categorie_display()})"
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 {depenses_crees} dépenses ont été créées avec succès !'
            )
        )
        
        # Afficher un résumé
        total_solidarite = Depense.objects.filter(categorie='SOLIDARITE').aggregate(
            total=models.Sum('montant')
        )['total'] or 0
        
        total_penalites = Depense.objects.filter(categorie='PENALITE').aggregate(
            total=models.Sum('montant')
        )['total'] or 0
        
        total_autre = Depense.objects.filter(categorie='AUTRE').aggregate(
            total=models.Sum('montant')
        )['total'] or 0
        
        self.stdout.write(f"\n📊 Résumé des dépenses créées:")
        self.stdout.write(f"   💰 Solidarité: {total_solidarite:,.0f} FCFA")
        self.stdout.write(f"   ⚠️  Pénalités: {total_penalites:,.0f} FCFA")
        self.stdout.write(f"   📝 Autres: {total_autre:,.0f} FCFA")
        self.stdout.write(f"   🎯 Total: {total_solidarite + total_penalites + total_autre:,.0f} FCFA")
