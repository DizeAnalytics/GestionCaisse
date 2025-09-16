from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from gestion_caisses.models import (
    RapportActivite, Caisse, Membre, Pret, Echeance, 
    MouvementFond, TransfertCaisse
)
from datetime import datetime, timedelta
import json


class Command(BaseCommand):
    help = 'Crée des rapports d\'activités réalistes basés sur les données existantes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--periode',
            type=int,
            default=6,
            help='Nombre de mois à couvrir (défaut: 6)'
        )
        parser.add_argument(
            '--caisses',
            action='store_true',
            help='Créer des rapports spécifiques aux caisses existantes'
        )

    def handle(self, *args, **options):
        periode_mois = options['periode']
        utiliser_caisses = options['caisses']
        
        # Récupérer les utilisateurs et caisses existants
        users = list(User.objects.filter(is_staff=True))
        caisses = list(Caisse.objects.all())
        
        if not users:
            self.stdout.write(
                self.style.ERROR('Aucun utilisateur staff trouvé. Créez d\'abord des utilisateurs.')
            )
            return
        
        if not caisses:
            self.stdout.write(
                self.style.ERROR('Aucune caisse trouvée. Créez d\'abord des caisses.')
            )
            return
        
        # Périodes de test
        aujourd_hui = timezone.now().date()
        date_fin = aujourd_hui
        date_debut = aujourd_hui - timedelta(days=30 * periode_mois)
        
        self.stdout.write(f"📅 Création de rapports pour la période: {date_debut} → {date_fin}")
        
        rapports_crees = 0
        
        # 1. Créer des rapports généraux (sans caisse spécifique)
        if not utiliser_caisses:
            rapports_crees += self._creer_rapports_globaux(
                users, date_debut, date_fin, periode_mois
            )
        
        # 2. Créer des rapports par caisse
        if utiliser_caisses:
            rapports_crees += self._creer_rapports_par_caisse(
                users, caisses, date_debut, date_fin, periode_mois
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ {rapports_crees} rapports d\'activités créés avec succès!'
            )
        )
        
        # Afficher des statistiques
        self._afficher_statistiques()

    def _creer_rapports_globaux(self, users, date_debut, date_fin, periode_mois):
        """Crée des rapports généraux pour tout le système"""
        rapports_crees = 0
        types_rapports = ['general', 'financier', 'prets', 'membres', 'echeances']
        
        for type_rapport in types_rapports:
            for mois in range(periode_mois):
                try:
                    # Calculer la période du mois
                    date_mois_debut = date_debut + timedelta(days=30 * mois)
                    date_mois_fin = min(date_mois_debut + timedelta(days=30), date_fin)
                    
                    # Générer les données selon le type
                    donnees = self._generer_donnees_reelles(
                        type_rapport, None, date_mois_debut, date_mois_fin
                    )
                    
                    # Créer le rapport
                    rapport = RapportActivite.objects.create(
                        caisse=None,  # Rapport global
                        type_rapport=type_rapport,
                        date_debut=date_mois_debut,
                        date_fin=date_mois_fin,
                        statut='GENERE',
                        genere_par=users[0],  # Premier utilisateur staff
                        date_generation=timezone.now() - timedelta(days=random.randint(0, 30)),
                        donnees=donnees,
                        notes=f"Rapport {type_rapport} global pour {date_mois_debut.strftime('%B %Y')}"
                    )
                    
                    rapports_crees += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Rapport global créé: {rapport}'
                        )
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Erreur lors de la création du rapport global {type_rapport}: {str(e)}')
                    )
        
        return rapports_crees

    def _creer_rapports_par_caisse(self, users, caisses, date_debut, date_fin, periode_mois):
        """Crée des rapports spécifiques aux caisses"""
        rapports_crees = 0
        types_rapports = ['general', 'financier', 'prets', 'membres', 'echeances']
        
        for caisse in caisses:
            for type_rapport in types_rapports:
                for mois in range(periode_mois):
                    try:
                        # Calculer la période du mois
                        date_mois_debut = date_debut + timedelta(days=30 * mois)
                        date_mois_fin = min(date_mois_debut + timedelta(days=30), date_fin)
                        
                        # Générer les données selon le type et la caisse
                        donnees = self._generer_donnees_reelles(
                            type_rapport, caisse, date_mois_debut, date_mois_fin
                        )
                        
                        # Créer le rapport
                        rapport = RapportActivite.objects.create(
                            caisse=caisse,
                            type_rapport=type_rapport,
                            date_debut=date_mois_debut,
                            date_fin=date_mois_fin,
                            statut='GENERE',
                            genere_par=users[0],  # Premier utilisateur staff
                            date_generation=timezone.now() - timedelta(days=random.randint(0, 30)),
                            donnees=donnees,
                            notes=f"Rapport {type_rapport} pour {caisse.nom_association} - {date_mois_debut.strftime('%B %Y')}"
                        )
                        
                        rapports_crees += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Rapport caisse créé: {rapport}'
                            )
                        )
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Erreur lors de la création du rapport {type_rapport} pour {caisse.nom_association}: {str(e)}')
                        )
        
        return rapports_crees

    def _generer_donnees_reelles(self, type_rapport, caisse, date_debut, date_fin):
        """Génère des données réelles basées sur les modèles existants"""
        try:
            if type_rapport == 'general':
                return self._donnees_rapport_general(caisse, date_debut, date_fin)
            elif type_rapport == 'financier':
                return self._donnees_rapport_financier(caisse, date_debut, date_fin)
            elif type_rapport == 'prets':
                return self._donnees_rapport_prets(caisse, date_debut, date_fin)
            elif type_rapport == 'membres':
                return self._donnees_rapport_membres(caisse, date_debut, date_fin)
            elif type_rapport == 'echeances':
                return self._donnees_rapport_echeances(caisse, date_debut, date_fin)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Erreur lors de la génération des données pour {type_rapport}: {str(e)}')
            )
            return {}
        
        return {}

    def _donnees_rapport_general(self, caisse, date_debut, date_fin):
        """Données pour le rapport général"""
        if caisse:
            # Rapport pour une caisse spécifique
            membres = Membre.objects.filter(caisse=caisse, date_adhesion__range=[date_debut, date_fin])
            prets = Pret.objects.filter(caisse=caisse, date_demande__range=[date_debut, date_fin])
        else:
            # Rapport global
            membres = Membre.objects.filter(date_adhesion__range=[date_debut, date_fin])
            prets = Pret.objects.filter(date_demande__range=[date_debut, date_fin])
        
        return {
            'total_caisses': Caisse.objects.count() if not caisse else 1,
            'total_membres': membres.count(),
            'total_prets': prets.count(),
            'total_fonds': float(Caisse.objects.aggregate(total=Sum('fond_disponible'))['total'] or 0) if not caisse else float(caisse.fond_disponible),
            'periode': f"{date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}",
            'generation_date': timezone.now().isoformat()
        }

    def _donnees_rapport_financier(self, caisse, date_debut, date_fin):
        """Données pour le rapport financier"""
        if caisse:
            mouvements = MouvementFond.objects.filter(
                caisse=caisse, date_mouvement__range=[date_debut, date_fin]
            )
            transferts = TransfertCaisse.objects.filter(
                Q(caisse_source=caisse) | Q(caisse_destination=caisse),
                date_transfert__range=[date_debut, date_fin]
            )
        else:
            mouvements = MouvementFond.objects.filter(date_mouvement__range=[date_debut, date_fin])
            transferts = TransfertCaisse.objects.filter(date_transfert__range=[date_debut, date_fin])
        
        return {
            'fonds_disponibles': float(Caisse.objects.aggregate(total=Sum('fond_disponible'))['total'] or 0) if not caisse else float(caisse.fond_disponible),
            'fonds_initiaux': float(Caisse.objects.aggregate(total=Sum('fond_initial'))['total'] or 0) if not caisse else float(caisse.fond_initial),
            'mouvements_total': mouvements.count(),
            'transferts_total': transferts.count(),
            'devise': 'FCFA',
            'periode': f"{date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}",
            'generation_date': timezone.now().isoformat()
        }

    def _donnees_rapport_prets(self, caisse, date_debut, date_fin):
        """Données pour le rapport des prêts"""
        if caisse:
            prets = Pret.objects.filter(caisse=caisse, date_demande__range=[date_debut, date_fin])
        else:
            prets = Pret.objects.filter(date_demande__range=[date_debut, date_fin])
        
        prets_en_cours = prets.filter(statut='EN_COURS').count()
        prets_rembourses = prets.filter(statut='REMBOURSE').count()
        prets_en_retard = prets.filter(statut='EN_RETARD').count()
        
        montant_total = float(prets.aggregate(total=Sum('montant_accord'))['total'] or 0)
        montant_rembourse = float(prets.aggregate(total=Sum('montant_rembourse'))['total'] or 0)
        
        taux_remboursement = (montant_rembourse / montant_total * 100) if montant_total > 0 else 0
        
        return {
            'prets_en_cours': prets_en_cours,
            'prets_rembourses': prets_rembourses,
            'prets_en_retard': prets_en_retard,
            'montant_total_prets': montant_total,
            'montant_rembourse': montant_rembourse,
            'taux_remboursement': round(taux_remboursement, 2),
            'periode': f"{date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}",
            'generation_date': timezone.now().isoformat()
        }

    def _donnees_rapport_membres(self, caisse, date_debut, date_fin):
        """Données pour le rapport des membres"""
        if caisse:
            membres = Membre.objects.filter(caisse=caisse, date_adhesion__range=[date_debut, date_fin])
        else:
            membres = Membre.objects.filter(date_adhesion__range=[date_debut, date_fin])
        
        membres_actifs = membres.filter(statut='ACTIF').count()
        membres_nouveaux = membres.count()
        
        repartition_par_role = {}
        for role in ['PRESIDENTE', 'SECRETAIRE', 'TRESORIERE', 'MEMBRE']:
            repartition_par_role[role] = membres.filter(role=role).count()
        
        return {
            'total_membres': membres.count(),
            'membres_actifs': membres_actifs,
            'membres_nouveaux': membres_nouveaux,
            'repartition_par_role': repartition_par_role,
            'periode': f"{date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}",
            'generation_date': timezone.now().isoformat()
        }

    def _donnees_rapport_echeances(self, caisse, date_debut, date_fin):
        """Données pour le rapport des échéances"""
        if caisse:
            echeances = Echeance.objects.filter(
                pret__caisse=caisse, date_echeance__range=[date_debut, date_fin]
            )
        else:
            echeances = Echeance.objects.filter(date_echeance__range=[date_debut, date_fin])
        
        echeances_payees = echeances.filter(statut='PAYE').count()
        echeances_en_attente = echeances.filter(statut='EN_ATTENTE').count()
        echeances_en_retard = echeances.filter(statut='EN_RETARD').count()
        
        montant_total = float(echeances.aggregate(total=Sum('montant_echeance'))['total'] or 0)
        montant_paye = float(echeances.aggregate(total=Sum('montant_paye'))['total'] or 0)
        
        return {
            'total_echeances': echeances.count(),
            'echeances_payees': echeances_payees,
            'echeances_en_attente': echeances_en_attente,
            'echeances_en_retard': echeances_en_retard,
            'montant_total_echeances': montant_total,
            'montant_paye': montant_paye,
            'periode': f"{date_debut.strftime('%d/%m/%Y')} → {date_fin.strftime('%d/%m/%Y')}",
            'generation_date': timezone.now().isoformat()
        }

    def _afficher_statistiques(self):
        """Affiche des statistiques sur les rapports créés"""
        total_rapports = RapportActivite.objects.count()
        rapports_par_type = RapportActivite.objects.values('type_rapport').annotate(
            count=Count('id')
        ).order_by('type_rapport')
        
        rapports_par_statut = RapportActivite.objects.values('statut').annotate(
            count=Count('id')
        ).order_by('statut')
        
        rapports_par_caisse = RapportActivite.objects.values('caisse__nom_association').annotate(
            count=Count('id')
        ).order_by('caisse__nom_association')
        
        self.stdout.write("\n📊 Statistiques des rapports:")
        self.stdout.write(f"Total des rapports: {total_rapports}")
        
        self.stdout.write("\nPar type:")
        for item in rapports_par_type:
            self.stdout.write(f"  - {item['type_rapport']}: {item['count']}")
        
        self.stdout.write("\nPar statut:")
        for item in rapports_par_statut:
            self.stdout.write(f"  - {item['statut']}: {item['count']}")
        
        self.stdout.write("\nPar caisse:")
        for item in rapports_par_caisse:
            nom_caisse = item['caisse__nom_association'] or 'Global'
            self.stdout.write(f"  - {nom_caisse}: {item['count']}")


# Import manquant
import random
