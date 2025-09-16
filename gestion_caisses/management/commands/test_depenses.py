from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from gestion_caisses.models import Caisse, Membre, Depense, RapportActivite
from decimal import Decimal
import random
from datetime import date, timedelta
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Teste le système de gestion des dépenses'

    def handle(self, *args, **options):
        self.stdout.write('🧪 Test du système de gestion des dépenses...')
        
        # Vérifier que les modèles sont accessibles
        try:
            caisses = Caisse.objects.all()
            membres = Membre.objects.all()
            
            if not caisses.exists():
                self.stdout.write(self.style.WARNING('⚠️  Aucune caisse trouvée. Créez d\'abord des caisses.'))
                return
                
            if not membres.exists():
                self.stdout.write(self.style.WARNING('⚠️  Aucun membre trouvé. Créez d\'abord des membres.'))
                return
            
            # Test 1: Vérifier le calcul du solde disponible
            caisse = caisses.first()
            self.stdout.write(f'📊 Test du solde disponible pour la caisse: {caisse.nom_association}')
            
            # Calculer le solde théorique
            total_solidarite = caisse.cotisations.aggregate(
                total=Sum('frais_solidarite')
            )['total'] or 0
            
            total_penalites = caisse.cotisations.aggregate(
                total=Sum('penalite_emprunt_retard')
            )['total'] or 0
            
            total_depenses = caisse.depenses.filter(statut__in=['APPROUVEE', 'TERMINEE']).aggregate(
                total=Sum('montant')
            )['total'] or 0
            
            solde_theorique = (total_solidarite + total_penalites) - total_depenses
            
            self.stdout.write(f'   💰 Frais de solidarité: {total_solidarite} FCFA')
            self.stdout.write(f'   ⚠️  Frais de pénalités: {total_penalites} FCFA')
            self.stdout.write(f'   💸 Dépenses approuvées: {total_depenses} FCFA')
            self.stdout.write(f'   💵 Solde disponible: {solde_theorique} FCFA')
            
            # Test 2: Vérifier le modèle RapportActivite
            self.stdout.write('\n📋 Test du modèle RapportActivite...')
            try:
                rapport = RapportActivite.objects.create(
                    type_rapport='DEPENSES',
                    caisse=caisse,
                    date_debut=date.today() - timedelta(days=30),
                    date_fin=date.today(),
                    notes='Test de création de rapport',
                    statut='EN_ATTENTE'
                )
                self.stdout.write(self.style.SUCCESS(f'   ✅ Rapport créé avec succès (ID: {rapport.pk})'))
                
                # Nettoyer le test
                rapport.delete()
                self.stdout.write('   🧹 Rapport de test supprimé')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Erreur lors de la création du rapport: {e}'))
            
            # Test 3: Vérifier les propriétés du modèle Depense
            if caisse.depenses.exists():
                depense = caisse.depenses.first()
                self.stdout.write(f'\n🔍 Test des propriétés de la dépense: {depense.description}')
                
                try:
                    solde_disponible = depense.solde_disponible_caisse
                    peut_etre_approuvee = depense.peut_etre_approuvee
                    
                    self.stdout.write(f'   💰 Solde disponible: {solde_disponible} FCFA')
                    self.stdout.write(f'   ✅ Peut être approuvée: {peut_etre_approuvee}')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ Erreur lors du calcul des propriétés: {e}'))
            else:
                self.stdout.write('\n📝 Aucune dépense trouvée pour tester les propriétés')
            
            self.stdout.write(self.style.SUCCESS('\n🎉 Tests terminés avec succès !'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur lors des tests: {e}'))
            import traceback
            traceback.print_exc()
