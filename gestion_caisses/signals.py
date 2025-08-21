from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Caisse, Membre, Pret, MouvementFond, AuditLog, CaisseGenerale


@receiver(post_save, sender=Caisse)
def caisse_post_save(sender, instance, created, **kwargs):
    """Signal post-save pour les caisses"""
    if created:
        # Log de création automatique
        AuditLog.objects.create(
            utilisateur=None,  # Sera mis à jour si disponible
            action='CREATION',
            modele='Caisse',
            objet_id=instance.id,
            details={
                'nom_association': instance.nom_association,
                'code': instance.code,
                'region': instance.region.nom if instance.region else None,
                'commune': instance.commune.nom if instance.commune else None
            }
        )


@receiver(post_save, sender=Membre)
def membre_post_save(sender, instance, created, **kwargs):
    """Signal post-save pour les membres"""
    if created:
        # Log de création automatique
        AuditLog.objects.create(
            utilisateur=None,
            action='CREATION',
            modele='Membre',
            objet_id=instance.id,
            details={
                'nom': instance.nom,
                'prenoms': instance.prenoms,
                'numero_carte_electeur': instance.numero_carte_electeur,
                'caisse': instance.caisse.nom_association if instance.caisse else None
            }
        )


@receiver(post_save, sender=Pret)
def pret_post_save(sender, instance, created, **kwargs):
    """Signal post-save pour les prêts"""
    if created:
        # Log de création automatique
        AuditLog.objects.create(
            utilisateur=None,
            action='CREATION',
            modele='Pret',
            objet_id=instance.id,
            details={
                'numero_pret': instance.numero_pret,
                'montant_demande': str(instance.montant_demande),
                'membre': instance.membre.nom_complet if instance.membre else None,
                'caisse': instance.caisse.nom_association if instance.caisse else None
            }
        )


@receiver(post_save, sender=MouvementFond)
def mouvement_fond_post_save(sender, instance, created, **kwargs):
    """Signal post-save pour les mouvements de fonds"""
    if created:
        # Log de création automatique
        AuditLog.objects.create(
            utilisateur=instance.utilisateur,
            action='CREATION',
            modele='MouvementFond',
            objet_id=instance.id,
            details={
                'type_mouvement': instance.type_mouvement,
                'montant': str(instance.montant),
                'caisse': instance.caisse.nom_association if instance.caisse else None,
                'solde_avant': str(instance.solde_avant),
                'solde_apres': str(instance.solde_apres)
            }
        )
        # Mettre à jour le total des caisses dans la Caisse Générale
        try:
            cg = CaisseGenerale.get_instance()
            cg.recalculer_total_caisses()
        except Exception:
            pass


@receiver(post_delete, sender=Caisse)
def caisse_post_delete(sender, instance, **kwargs):
    """Signal post-delete pour les caisses"""
    AuditLog.objects.create(
        utilisateur=None,
        action='SUPPRESSION',
        modele='Caisse',
        objet_id=instance.id,
        details={
            'nom_association': instance.nom_association,
            'code': instance.code
        }
    )


@receiver(post_delete, sender=Membre)
def membre_post_delete(sender, instance, **kwargs):
    """Signal post-delete pour les membres"""
    AuditLog.objects.create(
        utilisateur=None,
        action='SUPPRESSION',
        modele='Membre',
        objet_id=instance.id,
        details={
            'nom': instance.nom,
            'prenoms': instance.prenoms,
            'numero_carte_electeur': instance.numero_carte_electeur
        }
    )


@receiver(post_delete, sender=Pret)
def pret_post_delete(sender, instance, **kwargs):
    """Signal post-delete pour les prêts"""
    AuditLog.objects.create(
        utilisateur=None,
        action='SUPPRESSION',
        modele='Pret',
        objet_id=instance.id,
        details={
            'numero_pret': instance.numero_pret,
            'montant_demande': str(instance.montant_demande)
        }
    )
