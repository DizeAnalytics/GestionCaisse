from django.contrib.auth.models import User
from django.utils import timezone
from .models import Notification, Pret, Caisse, AuditLog, Agent


class AgentService:
    """Service pour gérer la logique métier des agents"""
    
    @staticmethod
    def creer_agent(nom, prenoms, numero_carte_electeur, date_naissance, adresse, numero_telephone, email, 
                   date_embauche, region=None, prefecture=None, notes="", 
                   creer_compte_utilisateur=True, utilisateur_creation=None):
        """Crée un nouvel agent avec optionnellement un compte utilisateur"""
        # Vérifier que le numéro de carte d'électeur est unique
        if numero_carte_electeur and Agent.objects.filter(numero_carte_electeur=numero_carte_electeur).exists():
            raise ValueError(f"Le numéro de carte d'électeur {numero_carte_electeur} existe déjà.")
        
        # Créer l'agent (le matricule sera généré automatiquement)
        agent = Agent.objects.create(
            nom=nom,
            prenoms=prenoms,
            numero_carte_electeur=numero_carte_electeur,
            date_naissance=date_naissance,
            adresse=adresse,
            numero_telephone=numero_telephone,
            email=email,
            date_embauche=date_embauche,
            region=region,
            prefecture=prefecture,
            notes=notes
        )
        
        # Créer le compte utilisateur si demandé
        if creer_compte_utilisateur:
            user = AgentService._creer_compte_utilisateur(agent)
            agent.utilisateur = user
            agent.save()
        
        # Log d'audit
        if utilisateur_creation:
            AuditLog.objects.create(
                utilisateur=utilisateur_creation,
                action='CREATION',
                modele='Agent',
                objet_id=agent.id,
                details={
                    'matricule': agent.matricule,
                    'nom_complet': agent.nom_complet,
                    'compte_utilisateur_creé': creer_compte_utilisateur
                }
            )
        
        return agent
    
    @staticmethod
    def _creer_compte_utilisateur(agent):
        """Crée un compte utilisateur pour un agent"""
        import random
        import string
        
        # Générer le nom d'utilisateur
        base_username = f"agent_{agent.nom.lower()}{agent.prenoms.split()[0].lower()}"
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Générer le mot de passe
        chars = string.ascii_letters + string.digits
        password = ''.join(random.choice(chars) for _ in range(8))
        
        # Créer l'utilisateur
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=agent.prenoms,
            last_name=agent.nom,
            email=agent.email,
            is_staff=True,  # Les agents ont accès à l'admin
            is_superuser=False
        )
        
        return user
    
    @staticmethod
    def assigner_caisse_agent(caisse, agent, utilisateur_modification=None):
        """Assigne une caisse à un agent"""
        if caisse.agent == agent:
            return caisse  # Déjà assignée
        
        ancien_agent = caisse.agent
        caisse.agent = agent
        caisse.save()
        
        # Log d'audit
        if utilisateur_modification:
            AuditLog.objects.create(
                utilisateur=utilisateur_modification,
                action='MODIFICATION',
                modele='Caisse',
                objet_id=caisse.id,
                details={
                    'operation': 'CHANGEMENT_AGENT',
                    'ancien_agent': ancien_agent.nom_complet if ancien_agent else 'Aucun',
                    'nouvel_agent': agent.nom_complet,
                    'caisse': caisse.nom_association
                }
            )
        
        return caisse
    
    @staticmethod
    def obtenir_statistiques_agent(agent):
        """Retourne les statistiques d'un agent"""
        caisses = agent.caisses.all()
        
        stats = {
            'nombre_caisses_total': caisses.count(),
            'nombre_caisses_actives': caisses.filter(statut='ACTIVE').count(),
            'nombre_caisses_inactives': caisses.filter(statut='INACTIVE').count(),
            'nombre_caisses_suspendues': caisses.filter(statut='SUSPENDUE').count(),
            'nombre_membres_total': sum(caisse.nombre_membres for caisse in caisses),
            'nombre_prets_actifs': sum(caisse.nombre_prets_actifs for caisse in caisses),
            'montant_total_fonds': sum(caisse.fond_disponible for caisse in caisses),
            'montant_total_prets': sum(caisse.montant_total_prets for caisse in caisses),
        }
        
        return stats
    
    @staticmethod
    def obtenir_agents_par_region(region=None):
        """Retourne les agents filtrés par région"""
        agents = Agent.objects.filter(statut='ACTIF')
        
        if region:
            agents = agents.filter(region=region)
        
        return agents.order_by('nom', 'prenoms')


class NotificationService:
    """Service pour gérer les notifications du système"""
    
    @staticmethod
    def _creer_notification_securisee(destinataire, type_notification, titre, message, caisse=None, pret=None, lien_action=''):
        """
        Méthode utilitaire pour créer une notification de manière sécurisée.
        Vérifie que le destinataire est bien un User avant de créer la notification.
        """
        if not isinstance(destinataire, User):
            # Si ce n'est pas un User, on ne crée pas la notification
            return None
        
        return Notification.objects.create(
            destinataire=destinataire,
            type_notification=type_notification,
            titre=titre,
            message=message,
            caisse=caisse,
            pret=pret,
            lien_action=lien_action
        )
    
    @staticmethod
    def notifier_demande_pret(pret):
        """Notifier l'administrateur d'une nouvelle demande de prêt"""
        # Trouver tous les administrateurs
        admins = User.objects.filter(is_superuser=True)
        
        for admin in admins:
            Notification.objects.create(
                destinataire=admin,
                type_notification='DEMANDE_PRET',
                titre=f'Nouvelle demande de prêt - {pret.membre.nom_complet}',
                message=f'Une nouvelle demande de prêt de {pret.montant_demande} FCFA a été soumise par {pret.membre.nom_complet} de la caisse {pret.caisse.nom_association}.',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/adminsecurelogin/gestion_caisses/pret/{pret.id}/change/'
            )
            
            # Log d'audit (utilisateur doit être un User)
            AuditLog.objects.create(
                utilisateur=admin,
                action='NOTIFICATION',
                modele='Pret',
                objet_id=pret.id,
                details={
                    'type': 'DEMANDE_PRET',
                    'destinataire': admin.username,
                    'montant': str(pret.montant_demande)
                }
            )
    
    @staticmethod
    def notifier_validation_pret(pret, admin):
        """Notifier la caisse de la validation d'un prêt"""
        # Notifier la présidente de la caisse (si elle a un utilisateur associé)
        if pret.caisse.presidente and pret.caisse.presidente.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.presidente.utilisateur,
                type_notification='VALIDATION_PRET',
                titre=f'Prêt validé - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été validé par l\'administrateur. Le prêt peut maintenant être octroyé.',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Notifier la secrétaire de la caisse (si elle a un utilisateur associé)
        if pret.caisse.secretaire and pret.caisse.secretaire.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.secretaire.utilisateur,
                type_notification='VALIDATION_PRET',
                titre=f'Prêt validé - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été validé par l\'administrateur. Le prêt peut maintenant être octroyé.',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Notifier la trésorière de la caisse (si elle a un utilisateur associé)
        if pret.caisse.tresoriere and pret.caisse.tresoriere.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.tresoriere.utilisateur,
                type_notification='VALIDATION_PRET',
                titre=f'Prêt validé - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été validé par l\'administrateur. Le prêt peut maintenant être octroyé.',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=admin,
            action='NOTIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'type': 'VALIDATION_PRET',
                'caisse': pret.caisse.nom_association,
                'montant': str(pret.montant_demande)
            }
        )
    
    @staticmethod
    def notifier_rejet_pret(pret, admin, motif_rejet):
        """Notifier la caisse du rejet d'un prêt"""
        # Notifier la présidente de la caisse (si elle a un utilisateur associé)
        if pret.caisse.presidente and pret.caisse.presidente.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.presidente.utilisateur,
                type_notification='REJET_PRET',
                titre=f'Prêt rejeté - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été rejeté par l\'administrateur. Motif: {motif_rejet}',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Notifier la secrétaire de la caisse (si elle a un utilisateur associé)
        if pret.caisse.secretaire and pret.caisse.secretaire.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.secretaire.utilisateur,
                type_notification='REJET_PRET',
                titre=f'Prêt rejeté - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été rejeté par l\'administrateur. Motif: {motif_rejet}',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Notifier la trésorière de la caisse (si elle a un utilisateur associé)
        if pret.caisse.tresoriere and pret.caisse.tresoriere.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.tresoriere.utilisateur,
                type_notification='REJET_PRET',
                titre=f'Prêt rejeté - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été rejeté par l\'administrateur. Motif: {motif_rejet}',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=admin,
            action='NOTIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'type': 'REJET_PRET',
                'caisse': pret.caisse.nom_association,
                'motif_rejet': motif_rejet
            }
        )
    
    @staticmethod
    def notifier_attente_pret(pret, admin, motif_attente):
        """Notifier la caisse de la mise en attente d'un prêt"""
        # Notifier la présidente de la caisse (si elle a un utilisateur associé)
        if pret.caisse.presidente and pret.caisse.presidente.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.presidente.utilisateur,
                type_notification='ATTENTE_PRET',
                titre=f'Prêt en attente - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été mis en attente par l\'administrateur. Motif: {motif_attente}',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Notifier la secrétaire de la caisse (si elle a un utilisateur associé)
        if pret.caisse.secretaire and pret.caisse.secretaire.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.secretaire.utilisateur,
                type_notification='ATTENTE_PRET',
                titre=f'Prêt en attente - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été mis en attente par l\'administrateur. Motif: {motif_attente}',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Notifier la trésorière de la caisse (si elle a un utilisateur associé)
        if pret.caisse.tresoriere and pret.caisse.tresoriere.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.tresoriere.utilisateur,
                type_notification='ATTENTE_PRET',
                titre=f'Prêt en attente - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_demande} FCFA demandé par {pret.membre.nom_complet} a été mis en attente par l\'administrateur. Motif: {motif_attente}',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=admin,
            action='NOTIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'type': 'ATTENTE_PRET',
                'caisse': pret.caisse.nom_association,
                'motif_attente': motif_attente
            }
        )
    
    @staticmethod
    def notifier_octroi_pret(pret, utilisateur_octroi):
        """Notifier l'octroi d'un prêt"""
        # Notifier la présidente de la caisse (si elle a un utilisateur associé)
        if pret.caisse.presidente and pret.caisse.presidente.utilisateur:
            NotificationService._creer_notification_securisee(
                destinataire=pret.caisse.presidente.utilisateur,
                type_notification='OCTROI_PRET',
                titre=f'Prêt octroyé - {pret.membre.nom_complet}',
                message=f'Le prêt de {pret.montant_accord:,.0f} FCFA a été octroyé à {pret.membre.nom_complet} par {utilisateur_octroi.username}.',
                caisse=pret.caisse,
                pret=pret,
                lien_action=f'/gestion-caisses/prets/'
            )
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=utilisateur_octroi,
            action='NOTIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'type': 'OCTROI_PRET',
                'caisse': pret.caisse.nom_association,
                'montant': str(pret.montant_accord)
            }
        )
    
    @staticmethod
    def notifier_fonds_insuffisants(pret, admin):
        """Notifier l'administrateur du manque de fonds pour un prêt bloqué"""
        NotificationService._creer_notification_securisee(
            destinataire=admin,
            type_notification='FONDS_INSUFFISANTS',
            titre=f'Fonds insuffisants pour le prêt {pret.numero_pret}',
            message=f'Le prêt {pret.numero_pret} a été bloqué car le solde disponible de la caisse ({pret.caisse.fond_disponible:,.0f} FCFA) est inférieur au montant demandé ({pret.montant_accord:,.0f} FCFA).',
            caisse=pret.caisse,
            pret=pret,
            lien_action=f'/adminsecurelogin/gestion_caisses/pret/{pret.id}/change/'
        )


class PretService:
    """Service pour gérer la logique métier des prêts"""
    
    @staticmethod
    def soumettre_demande_pret(pret, utilisateur):
        """Soumettre une demande de prêt pour validation admin"""
        # Mettre le prêt en attente de validation admin
        pret.statut = 'EN_ATTENTE_ADMIN'
        pret.save()
        
        # Notifier l'administrateur
        NotificationService.notifier_demande_pret(pret)
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=utilisateur,
            action='CREATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'statut': 'EN_ATTENTE_ADMIN',
                'montant': str(pret.montant_demande),
                'caisse': pret.caisse.nom_association
            }
        )
        
        return pret
    
    @staticmethod
    def valider_pret(pret, admin):
        """Valider un prêt par l'administrateur"""
        from decimal import Decimal, ROUND_HALF_UP
        
        # 1. Vérifier que le montant accordé est inférieur ou égal au montant demandé
        if pret.montant_accord and pret.montant_accord > pret.montant_demande:
            raise ValueError("Le montant accordé ne peut pas être supérieur au montant demandé")
        
        # 2. Par défaut, le montant accordé = montant demandé si non spécifié
        if not pret.montant_accord:
            pret.montant_accord = pret.montant_demande
        
        # 2.bis. Règle plafond: montant accordé ne peut pas dépasser 2x le total des cotisations du membre
        try:
            total_cot = pret.membre.total_cotisations() if hasattr(pret.membre, 'total_cotisations') else 0
            plafond = (total_cot or 0) * 2
            if pret.montant_accord and float(pret.montant_accord) > float(plafond):
                raise ValueError(f"Montant accordé au-dessus du plafond autorisé ({plafond:,.0f} FCFA = 2x cotisations cumulées)")
        except Exception:
            # Si le calcul échoue, on laisse la validation modèle en dernier ressort
            pass
        
        # 3. Vérifier le fond disponible dans la caisse
        if pret.caisse.fond_disponible < pret.montant_accord:
            # Bloquer le prêt et notifier l'admin
            pret.statut = 'BLOQUE'
            pret.motif_rejet = f'Fonds insuffisants dans la caisse. Solde disponible: {pret.caisse.fond_disponible:,.0f} FCFA, Montant demandé: {pret.montant_accord:,.0f} FCFA'
            pret.save()
            
            # Notifier l'administrateur du manque de fonds
            NotificationService.notifier_fonds_insuffisants(pret, admin)
            
            # Log d'audit
            AuditLog.objects.create(
                utilisateur=admin,
                action='BLOQUE',
                modele='Pret',
                objet_id=pret.id,
                details={
                    'motif': 'Fonds insuffisants',
                    'solde_disponible': str(pret.caisse.fond_disponible),
                    'montant_demande': str(pret.montant_accord),
                    'caisse': pret.caisse.nom_association
                }
            )
            
            return pret
        
        # 4. Calculer le total à rembourser (montant accordé + intérêts)
        montant_principal = pret.montant_accord
        montant_interet = montant_principal * (pret.taux_interet / Decimal('100'))
        total_a_rembourser = montant_principal + montant_interet
        
        # 5. Valider le prêt (pas de mouvement de fonds ici, seulement à l'octroi)
        pret.statut = 'VALIDE'
        pret.date_validation = timezone.now()
        pret.save()
        
        # 6. Notifier la validation
        NotificationService.notifier_validation_pret(pret, admin)
        
        # 7. Log d'audit
        AuditLog.objects.create(
            utilisateur=admin,
            action='VALIDATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'statut': 'VALIDE',
                'montant_demande': str(pret.montant_demande),
                'montant_accord': str(pret.montant_accord),
                'taux_interet': str(pret.taux_interet),
                'total_a_rembourser': str(total_a_rembourser),
                'caisse': pret.caisse.nom_association
            }
        )
        
        return pret
    
    @staticmethod
    def rejeter_pret(pret, admin, motif_rejet):
        """Rejeter un prêt par l'administrateur"""
        pret.statut = 'REJETE'
        pret.motif_rejet = motif_rejet
        pret.save()
        
        # Notifier le rejet
        NotificationService.notifier_rejet_pret(pret, admin, motif_rejet)
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=admin,
            action='REJET',
            modele='Pret',
            objet_id=pret.id,
            details={
                'motif_rejet': motif_rejet,
                'caisse': pret.caisse.nom_association
            }
        )
        
        return pret
    
    @staticmethod
    def mettre_en_attente_pret(pret, admin, motif_attente):
        """Mettre un prêt en attente par l'administrateur"""
        pret.statut = 'EN_ATTENTE'
        pret.notes = f"Mis en attente par {admin.username}: {motif_attente}"
        pret.save()
        
        # Notifier la mise en attente
        NotificationService.notifier_attente_pret(pret, admin, motif_attente)
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=admin,
            action='MODIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'statut': 'EN_ATTENTE',
                'motif_attente': motif_attente,
                'caisse': pret.caisse.nom_association
            }
        )
        
        return pret
    
    @staticmethod
    def octroyer_pret(pret, utilisateur_octroi):
        """Octroyer un prêt validé au client"""
        if pret.statut != 'VALIDE':
            raise ValueError("Seuls les prêts validés peuvent être octroyés")
        
        # S'assurer que le montant_accord est défini
        if not pret.montant_accord:
            pret.montant_accord = pret.montant_demande

        # Re-vérifier le solde au moment de l'octroi
        if pret.caisse.fond_disponible < pret.montant_accord:
            raise ValueError("Fonds insuffisants au moment de l'octroi")

        # Impacter le solde maintenant (octroi)
        solde_avant = pret.caisse.fond_disponible
        pret.caisse.fond_disponible = solde_avant - pret.montant_accord
        pret.caisse.save()

        # Journaliser le mouvement de fonds
        from .models import MouvementFond
        MouvementFond.objects.create(
            caisse=pret.caisse,
            type_mouvement='DECAISSEMENT',
            montant=pret.montant_accord,
            solde_avant=solde_avant,
            solde_apres=pret.caisse.fond_disponible,
            description=f'Décaissement du prêt {pret.numero_pret} pour {pret.membre.nom_complet}',
            pret=pret,
            utilisateur=utilisateur_octroi
        )

        # Mettre le prêt en cours
        pret.statut = 'EN_COURS'
        pret.date_decaissement = timezone.now()
        pret.save()
        
        # Calculer la date de fin du prêt (échéance globale)
        try:
            pret.mettre_a_jour_date_fin()
        except Exception:
            pass

        # Calculer automatiquement les échéances
        echeances_crees = pret.calculer_echeances()
        
        # Notifier l'octroi
        NotificationService.notifier_octroi_pret(pret, utilisateur_octroi)
        
        # Log d'audit
        AuditLog.objects.create(
            utilisateur=utilisateur_octroi,
            action='MODIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'statut': 'EN_COURS',
                'date_decaissement': pret.date_decaissement.isoformat(),
                'caisse': pret.caisse.nom_association
            }
        )
        
        return pret

    @staticmethod
    def rembourser_pret(pret, utilisateur, montant, interet=0):
        """Enregistrer un remboursement (montant peut inclure une part d'intérêt).
        - Incrémente le montant remboursé du prêt
        - Crée un Mouvement de type REMBOURSEMENT et crédite la caisse
        - Si le prêt est totalement remboursé (montant_rembourse >= montant_accord), passe en REMBOURSE
        """
        from django.utils import timezone
        from decimal import Decimal
        if pret.statut not in ['EN_COURS', 'EN_RETARD']:
            raise ValueError("Seuls les prêts en cours ou en retard peuvent être remboursés")

        # Normaliser les montants en Decimal
        montant = Decimal(str(montant))
        interet = Decimal(str(interet or 0))

        if montant <= 0:
            raise ValueError("Le montant de remboursement doit être positif")

        # Empêcher de dépasser le reste à payer (principal + intérêts)
        # Total dû restant avant paiement = (montant accordé + intérêts) - principal déjà remboursé
        total_du_restant = (pret.total_a_rembourser or Decimal('0')) - (pret.montant_rembourse or Decimal('0'))
        paiement_total = montant + interet
        if paiement_total > total_du_restant:
            raise ValueError(f"Le montant dépasse le reste à payer ({total_du_restant} FCFA)")

        # Créditer la caisse
        solde_avant = pret.caisse.fond_disponible
        # Créditer la totalité encaissée (principal + intérêts) dans la caisse
        pret.caisse.fond_disponible = solde_avant + paiement_total
        # Conserver l'agrégat 'montant_total_remboursements' sur le principal remboursé uniquement
        pret.caisse.montant_total_remboursements = pret.caisse.montant_total_remboursements + montant
        pret.caisse.save()

        # Mouvement de fonds
        from .models import MouvementFond
        mouvement = MouvementFond.objects.create(
            caisse=pret.caisse,
            type_mouvement='REMBOURSEMENT',
            # Enregistrer le montant total encaissé pour refléter le flux financier réel
            montant=paiement_total,
            solde_avant=solde_avant,
            solde_apres=pret.caisse.fond_disponible,
            pret=pret,
            utilisateur=utilisateur,
            description=f"Remboursement du prêt {pret.numero_pret} (principal: {montant} FCFA, intérêt: {interet} FCFA)"
        )

        # Mettre à jour le prêt
        pret.montant_rembourse = pret.montant_rembourse + montant
        # Si ce paiement solde la dette totale (principal + intérêts), marquer comme remboursé
        restant_apres = total_du_restant - paiement_total
        if restant_apres <= 0:
            pret.statut = 'REMBOURSE'
            pret.date_remboursement_complet = timezone.now()
        pret.save()

        # Audit
        AuditLog.objects.create(
            utilisateur=utilisateur,
            action='MODIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'operation': 'REMBOURSEMENT',
                'montant': str(montant),
                'interet': str(interet),
                'montant_rembourse_total': str(pret.montant_rembourse),
                'statut': pret.statut
            }
        )

        return pret, mouvement
