from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Pret, Caisse, Membre, AuditLog
from django.db.models import Sum


@shared_task
def verifier_prets_en_retard():
    """Vérifier et marquer les prêts en retard"""
    print("Vérification des prêts en retard...")
    
    prets_en_cours = Pret.objects.filter(statut='EN_COURS')
    prets_en_retard = 0
    
    for pret in prets_en_cours:
        # Logique pour déterminer si un prêt est en retard
        # Par exemple, vérifier si une échéance est dépassée
        if pret.est_en_retard:
            pret.statut = 'EN_RETARD'
            pret.save()
            prets_en_retard += 1
            
            # Log de l'action
            AuditLog.objects.create(
                action='MODIFICATION',
                modele='Pret',
                objet_id=pret.id,
                details={
                    'statut_precedent': 'EN_COURS',
                    'nouveau_statut': 'EN_RETARD',
                    'raison': 'Échéance dépassée'
                }
            )
    
    print(f"{prets_en_retard} prêts marqués comme en retard")
    return prets_en_retard


@shared_task
def calculer_statistiques_caisses():
    """Calculer et mettre à jour les statistiques des caisses"""
    print("Calcul des statistiques des caisses...")
    
    caisses = Caisse.objects.all()
    total_prets = 0
    total_remboursements = 0
    
    for caisse in caisses:
        # Calculer le montant total des prêts actifs
        montant_prets = Pret.objects.filter(
            caisse=caisse, 
            statut__in=['EN_COURS', 'EN_RETARD']
        ).aggregate(
            total=Sum('montant_accord')
        )['total'] or 0
        
        # Calculer le montant total des remboursements
        montant_remboursements = Pret.objects.filter(
            caisse=caisse, 
            statut='REMBOURSE'
        ).aggregate(
            total=Sum('montant_rembourse')
        )['total'] or 0
        
        # Mettre à jour la caisse
        caisse.montant_total_prets = montant_prets
        caisse.montant_total_remboursements = montant_remboursements
        caisse.save()
        
        total_prets += montant_prets
        total_remboursements += montant_remboursements
    
    print(f"Statistiques mises à jour: {total_prets} en prêts, {total_remboursements} remboursés")
    return {
        'total_prets': total_prets,
        'total_remboursements': total_remboursements
    }


@shared_task
def nettoyer_audit_logs():
    """Nettoyer les anciens logs d'audit (garder 1 an)"""
    print("Nettoyage des anciens logs d'audit...")
    
    date_limite = timezone.now() - timedelta(days=365)
    logs_supprimes = AuditLog.objects.filter(
        date_action__lt=date_limite
    ).delete()[0]
    
    print(f"{logs_supprimes} anciens logs supprimés")
    return logs_supprimes


@shared_task
def verifier_fonds_insuffisants():
    """Vérifier les caisses avec des fonds insuffisants"""
    print("Vérification des fonds insuffisants...")
    
    seuil_minimum = 10000  # 10 000 FCFA
    caisses_fond_insuffisant = Caisse.objects.filter(
        fond_disponible__lt=seuil_minimum
    )
    
    for caisse in caisses_fond_insuffisant:
        # Log de l'alerte
        AuditLog.objects.create(
            action='CONSULTATION',
            modele='Caisse',
            objet_id=caisse.id,
            details={
                'alerte': 'Fonds insuffisants',
                'solde_actuel': str(caisse.fond_disponible),
                'seuil_minimum': str(seuil_minimum)
            }
        )
    
    print(f"{caisses_fond_insuffisant.count()} caisses avec fonds insuffisants détectées")
    return caisses_fond_insuffisant.count()


@shared_task
def generer_rapport_mensuel():
    """Générer un rapport mensuel des activités"""
    print("Génération du rapport mensuel...")
    
    mois_courant = timezone.now().month
    annee_courante = timezone.now().year
    
    # Statistiques du mois
    nouvelles_caisses = Caisse.objects.filter(
        date_creation__month=mois_courant,
        date_creation__year=annee_courante
    ).count()
    
    nouveaux_membres = Membre.objects.filter(
        date_adhesion__month=mois_courant,
        date_adhesion__year=annee_courante
    ).count()
    
    nouveaux_prets = Pret.objects.filter(
        date_demande__month=mois_courant,
        date_demande__year=annee_courante
    ).count()
    
    rapport = {
        'mois': mois_courant,
        'annee': annee_courante,
        'nouvelles_caisses': nouvelles_caisses,
        'nouveaux_membres': nouveaux_membres,
        'nouveaux_prets': nouveaux_prets,
        'date_generation': timezone.now().isoformat()
    }
    
    print(f"Rapport mensuel généré: {rapport}")
    return rapport


@shared_task
def envoyer_notifications_retard():
    """Envoyer des notifications pour les prêts en retard"""
    print("Envoi des notifications de retard...")
    
    prets_en_retard = Pret.objects.filter(statut='EN_RETARD')
    notifications_envoyees = 0
    
    for pret in prets_en_retard:
        # Ici, vous pourriez implémenter l'envoi d'emails/SMS
        # Pour l'instant, on se contente de logger l'action
        
        AuditLog.objects.create(
            action='CONSULTATION',
            modele='Pret',
            objet_id=pret.id,
            details={
                'notification': 'Prêt en retard',
                'membre': pret.membre.nom_complet,
                'montant_restant': str(pret.montant_restant)
            }
        )
        
        notifications_envoyees += 1
    
    print(f"{notifications_envoyees} notifications de retard envoyées")
    return notifications_envoyees
