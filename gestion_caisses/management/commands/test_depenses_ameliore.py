from django.core.management.base import BaseCommand
from gestion_caisses.models import Caisse, Depense, Membre, Cotisation
from django.contrib.auth.models import User
from decimal import Decimal


class Command(BaseCommand):
    help = 'Test du modèle Depense amélioré et de la logique de calcul du solde disponible'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Test du modèle Depense amélioré ==='))
        
        # Récupérer une caisse existante
        caisse = Caisse.objects.first()
        if not caisse:
            self.stdout.write(self.style.ERROR('Aucune caisse trouvée. Créez d\'abord des caisses.'))
            return
        
        self.stdout.write(f'Caisse testée: {caisse.nom_association} ({caisse.code})')
        
        # Afficher les informations de base de la caisse
        self.stdout.write(f'\n--- Informations de base ---')
        self.stdout.write(f'Fond initial: {caisse.fond_initial} FCFA')
        self.stdout.write(f'Fond disponible: {caisse.fond_disponible} FCFA')
        self.stdout.write(f'Nombre de membres: {caisse.nombre_membres}')
        
        # Afficher les totaux des cotisations
        self.stdout.write(f'\n--- Totaux des cotisations ---')
        self.stdout.write(f'Total frais de solidarité: {caisse.total_frais_solidarite} FCFA')
        self.stdout.write(f'Total frais de pénalités: {caisse.total_frais_penalites} FCFA')
        self.stdout.write(f'Total des cotisations: {caisse.total_frais_solidarite + caisse.total_frais_penalites} FCFA')
        
        # Afficher les informations sur les dépenses
        self.stdout.write(f'\n--- Informations sur les dépenses ---')
        self.stdout.write(f'Solde disponible pour dépenses: {caisse.solde_disponible_depenses} FCFA')
        self.stdout.write(f'Total dépenses approuvées: {caisse.total_depenses_approuvees} FCFA')
        self.stdout.write(f'Total dépenses en cours: {caisse.total_depenses_en_cours} FCFA')
        
        # Vérifier la logique de calcul
        self.stdout.write(f'\n--- Vérification de la logique ---')
        solde_calcule = (caisse.total_frais_solidarite + caisse.total_frais_penalites) - caisse.total_depenses_approuvees
        self.stdout.write(f'Solde calculé manuellement: {solde_calcule} FCFA')
        self.stdout.write(f'Solde via propriété: {caisse.solde_disponible_depenses} FCFA')
        
        if solde_calcule == caisse.solde_disponible_depenses:
            self.stdout.write(self.style.SUCCESS('✓ Calcul du solde correct !'))
        else:
            self.stdout.write(self.style.ERROR('✗ Erreur dans le calcul du solde !'))
        
        # Tester la création d'une dépense
        self.stdout.write(f'\n--- Test création dépense ---')
        try:
            # Récupérer un membre pour être responsable
            membre = caisse.membres.first()
            if not membre:
                self.stdout.write(self.style.WARNING('Aucun membre trouvé dans la caisse'))
            else:
                # Créer une dépense de test
                depense = Depense.objects.create(
                    caisse=caisse,
                    categorie='FORMATION',
                    type_depense='ORDINAIRE',
                    montant=Decimal('5000'),
                    titre='Formation en gestion financière',
                    description='Formation des membres sur la gestion financière',
                    objectif='Améliorer les compétences des membres en gestion',
                    beneficiaires='Tous les membres de la caisse',
                    justificatif='Formation nécessaire pour le bon fonctionnement',
                    date_depense=caisse.date_creation.date(),
                    responsable=membre,
                    priorite='HAUTE',
                    est_urgente=True
                )
                
                self.stdout.write(f'✓ Dépense créée: {depense.titre}')
                self.stdout.write(f'  - Montant: {depense.montant} FCFA')
                self.stdout.write(f'  - Catégorie: {depense.get_categorie_display()}')
                self.stdout.write(f'  - Type: {depense.get_type_depense_display()}')
                self.stdout.write(f'  - Priorité: {depense.get_priorite_display()}')
                self.stdout.write(f'  - Statut: {depense.get_statut_display()}')
                
                # Tester les propriétés
                self.stdout.write(f'\n--- Propriétés de la dépense ---')
                self.stdout.write(f'Solde disponible caisse: {depense.solde_disponible_caisse} FCFA')
                self.stdout.write(f'Peut être approuvée: {depense.peut_etre_approuvee}')
                self.stdout.write(f'Montant restant disponible: {depense.montant_restant_disponible} FCFA')
                self.stdout.write(f'Est en retard: {depense.est_en_retard}')
                
                # Tester l'approbation si possible
                if depense.peut_etre_approuvee:
                    self.stdout.write(f'\n--- Test approbation ---')
                    depense.approuver(membre, "Approuvé pour test")
                    self.stdout.write(f'✓ Dépense approuvée par {membre.nom_complet}')
                    self.stdout.write(f'  - Nouveau statut: {depense.get_statut_display()}')
                    self.stdout.write(f'  - Date approbation: {depense.date_approbation}')
                    
                    # Vérifier le nouveau solde
                    nouveau_solde = caisse.solde_disponible_depenses
                    self.stdout.write(f'  - Nouveau solde disponible: {nouveau_solde} FCFA')
                else:
                    self.stdout.write(self.style.WARNING('⚠ Dépense ne peut pas être approuvée (solde insuffisant)'))
                
                # Nettoyer la dépense de test
                depense.delete()
                self.stdout.write(f'✓ Dépense de test supprimée')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur lors de la création de la dépense: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n=== Test terminé avec succès ==='))
