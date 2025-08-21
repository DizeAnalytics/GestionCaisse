from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
import uuid


class Region(models.Model):
    """Modèle pour les régions du Togo"""
    nom = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Région"
        verbose_name_plural = "Régions"
        ordering = ['nom']
    
    def __str__(self):
        return self.nom


class Prefecture(models.Model):
    """Modèle pour les préfectures"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='prefectures')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Préfecture"
        verbose_name_plural = "Préfectures"
        ordering = ['nom']
        unique_together = ['nom', 'region']
    
    def __str__(self):
        return f"{self.nom} ({self.region.nom})"


class Commune(models.Model):
    """Modèle pour les communes"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    prefecture = models.ForeignKey(Prefecture, on_delete=models.CASCADE, related_name='communes')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Commune"
        verbose_name_plural = "Communes"
        ordering = ['nom']
        unique_together = ['nom', 'prefecture']
    
    def __str__(self):
        return f"{self.nom} ({self.prefecture.nom})"


class Canton(models.Model):
    """Modèle pour les cantons"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='cantons')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Canton"
        verbose_name_plural = "Cantons"
        ordering = ['nom']
        unique_together = ['nom', 'commune']
    
    def __str__(self):
        return f"{self.nom} ({self.commune.nom})"


class Village(models.Model):
    """Modèle pour les villages"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    canton = models.ForeignKey(Canton, on_delete=models.CASCADE, related_name='villages')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Village"
        verbose_name_plural = "Villages"
        ordering = ['nom']
        unique_together = ['nom', 'canton']
    
    def __str__(self):
        return f"{self.nom} ({self.canton.nom})"


class Agent(models.Model):
    """Modèle pour les agents qui gèrent les caisses"""
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('SUSPENDU', 'Suspendu'),
    ]
    
    # Informations personnelles
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=200)
    numero_carte_electeur = models.CharField(max_length=20, unique=True,
                                           help_text="Numéro de carte d'électeur unique de l'agent")
    date_naissance = models.DateField()
    adresse = models.TextField()
    numero_telephone = models.CharField(
        max_length=8, 
        help_text="Numéro de téléphone à 8 chiffres (format togolais)",
        validators=[
            RegexValidator(
                regex=r'^[0-9]{8}$',
                message='Le numéro de téléphone doit contenir exactement 8 chiffres (format togolais)'
            )
        ]
    )
    email = models.EmailField(blank=True)
    
    # Informations professionnelles
    matricule = models.CharField(max_length=20, unique=True, editable=False, help_text="Matricule unique de l'agent (généré automatiquement)")
    date_embauche = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF')
    
    # Lien vers l'utilisateur système (créé par l'admin)
    utilisateur = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='profil_agent')
    
    # Zone de responsabilité (optionnel)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='agents')
    prefecture = models.ForeignKey(Prefecture, on_delete=models.SET_NULL, null=True, blank=True, related_name='agents')
    
    # Informations de gestion
    date_creation = models.DateTimeField(auto_now_add=True)
    date_derniere_activite = models.DateTimeField(auto_now=True)
    
    # Métadonnées
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
        ordering = ['nom', 'prenoms']
    
    def __str__(self):
        return f"{self.nom} {self.prenoms} - {self.matricule}"
    
    def save(self, *args, **kwargs):
        """Génère automatiquement le matricule si il n'existe pas"""
        if not self.matricule:
            # Génération automatique du matricule : AGT[N][Année][Numéro séquentiel]
            current_year = timezone.now().year
            global_count = Agent.objects.count() + 1
            self.matricule = f"AGT{global_count}{current_year}{global_count:04d}"
        
        super().save(*args, **kwargs)
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}"
    
    @property
    def nombre_caisses(self):
        """Retourne le nombre de caisses gérées par cet agent"""
        return self.caisses.count()
    
    @property
    def caisses_actives(self):
        """Retourne le nombre de caisses actives gérées par cet agent"""
        return self.caisses.filter(statut='ACTIVE').count()


class Caisse(models.Model):
    """Modèle principal pour les caisses de femmes"""
    ROLE_CHOICES = [
        ('PRESIDENTE', 'Présidente'),
        ('SECRETAIRE', 'Secrétaire'),
        ('TRESORIERE', 'Trésorière'),
        ('MEMBRE', 'Membre simple'),
    ]
    
    # Code unique automatique : FKMCK[N][Nom_Association]
    code = models.CharField(max_length=50, unique=True, editable=False)
    nom_association = models.CharField(max_length=200)
    
    # Agent responsable de cette caisse
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='caisses', verbose_name="Agent responsable")
    
    # Localisation
    village = models.ForeignKey(Village, on_delete=models.CASCADE, related_name='caisses')
    canton = models.ForeignKey(Canton, on_delete=models.CASCADE, related_name='caisses')
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='caisses')
    prefecture = models.ForeignKey(Prefecture, on_delete=models.CASCADE, related_name='caisses')
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='caisses')
    
    # Informations de création
    date_creation = models.DateTimeField(auto_now_add=True)
    date_activation = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SUSPENDUE', 'Suspendue'),
    ], default='INACTIVE')
    
    # Membres dirigeants
    presidente = models.ForeignKey('Membre', on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='caisses_presidees')
    secretaire = models.ForeignKey('Membre', on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='caisses_secretariees')
    tresoriere = models.ForeignKey('Membre', on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='caisses_tresoriees')
    
    # Informations financières
    fond_initial = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fond_disponible = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    montant_total_prets = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    montant_total_remboursements = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Métadonnées
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Caisse"
        verbose_name_plural = "Caisses"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.code} - {self.nom_association}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Vérifier si c'est une nouvelle caisse
        
        if not self.code:
            # Génération automatique du code : FKMCK[N][Nom_Association]
            global_count = Caisse.objects.count() + 1
            nom_clean = ''.join(c for c in self.nom_association if c.isalnum())[:20]
            self.code = f"FKMCK{global_count}{nom_clean}"
        
        super().save(*args, **kwargs)
        
        # Si c'est une nouvelle caisse et qu'elle a un fond initial, l'ajouter au fond disponible
        if is_new and self.fond_initial > 0:
            self.fond_disponible = self.fond_initial
            # Sauvegarder à nouveau pour mettre à jour le fond disponible
            super().save(update_fields=['fond_disponible'])
    
    @property
    def nombre_membres(self):
        return self.membres.filter(statut='ACTIF').count()
    
    @property
    def nombre_prets_actifs(self):
        return self.prets.filter(statut='EN_COURS').count()
    
    @property
    def solde_disponible(self):
        return self.fond_disponible - self.montant_total_prets


class Membre(models.Model):
    """Modèle pour les membres des caisses"""
    ROLE_CHOICES = [
        ('PRESIDENTE', 'Présidente'),
        ('SECRETAIRE', 'Secrétaire'),
        ('TRESORIERE', 'Trésorière'),
        ('MEMBRE', 'Membre simple'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('SUSPENDU', 'Suspendu'),
        ('RETRAITE', 'Retraité'),
    ]
    
    # Identification unique
    numero_carte_electeur = models.CharField(max_length=20, unique=True, 
                                           help_text="Numéro de carte d'électeur")
    
    # Informations personnelles
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=200)
    date_naissance = models.DateField()
    adresse = models.TextField()
    numero_telephone = models.CharField(
        max_length=8, 
        help_text="Numéro de téléphone à 8 chiffres (format togolais)",
        validators=[
            RegexValidator(
                regex=r'^[0-9]{8}$',
                message='Le numéro de téléphone doit contenir exactement 8 chiffres (format togolais)'
            )
        ]
    )
    sexe = models.CharField(
        max_length=1,
        choices=[('F', 'Féminin'), ('M', 'Masculin')],
        default='F'
    )
    photo = models.ImageField(upload_to='photos_membres/', null=True, blank=True)
    signature = models.ImageField(upload_to='signatures_membres/', null=True, blank=True, verbose_name="Signature")
    
    # Rôle et statut
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBRE')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF')
    
    # Appartenance à la caisse
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='membres')

    # Lien optionnel vers un utilisateur (pour présidente/secrétaire/trésorière)
    utilisateur = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='profil_membre')
    
    # Informations de gestion
    date_adhesion = models.DateTimeField(auto_now_add=True)
    date_derniere_activite = models.DateTimeField(auto_now=True)
    
    # Métadonnées
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Membre"
        verbose_name_plural = "Membres"
        ordering = ['nom', 'prenoms']
        unique_together = ['numero_carte_electeur', 'caisse']
    
    def __str__(self):
        return f"{self.nom} {self.prenoms} - {self.caisse.nom_association}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Vérifier que la caisse n'a pas plus de 30 membres
        if self.caisse and self.statut == 'ACTIF':
            membres_actifs = self.caisse.membres.filter(statut='ACTIF').exclude(pk=self.pk).count()
            if membres_actifs >= 30:
                raise ValidationError("Une caisse ne peut pas avoir plus de 30 membres actifs.")
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}"


class Pret(models.Model):
    """Modèle pour les prêts accordés aux membres"""
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_ATTENTE_ADMIN', 'En attente validation admin'),
        ('VALIDE', 'Validé'),
        ('REJETE', 'Rejeté'),
        ('BLOQUE', 'Bloqué'),
        ('EN_COURS', 'En cours'),
        ('REMBOURSE', 'Remboursé'),
        ('EN_RETARD', 'En retard'),
    ]
    
    # Informations du prêt
    numero_pret = models.CharField(max_length=20, unique=True, editable=False)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='prets')
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='prets')
    
    # Détails financiers
    montant_demande = models.DecimalField(max_digits=15, decimal_places=2)
    montant_accord = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    taux_interet = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                     validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Durée et échéances
    duree_mois = models.PositiveIntegerField(help_text="Durée en mois")
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    date_decaissement = models.DateTimeField(null=True, blank=True)
    date_remboursement_complet = models.DateTimeField(null=True, blank=True)
    # Échéance globale (date de fin du prêt)
    date_fin_pret = models.DateField(null=True, blank=True)
    
    # Statut et motif
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    motif = models.TextField()
    motif_rejet = models.TextField(blank=True)
    
    # Suivi des remboursements
    montant_rembourse = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    nombre_echeances = models.PositiveIntegerField(default=0)
    nombre_echeances_payees = models.PositiveIntegerField(default=0)
    
    # Métadonnées
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Prêt"
        verbose_name_plural = "Prêts"
        ordering = ['-date_demande']
    
    def delete(self, *args, **kwargs):
        """Surcharge de la méthode delete pour gérer la suppression des prêts rejetés"""
        # Si le prêt est rejeté, on peut le supprimer
        if self.statut == 'REJETE':
            # Supprimer d'abord les notifications liées
            from .models import Notification
            Notification.objects.filter(pret=self).delete()
            
            # Supprimer les échéances liées
            from .models import Echeance
            Echeance.objects.filter(pret=self).delete()
            
            # Supprimer les mouvements de fonds liés
            from .models import MouvementFond
            MouvementFond.objects.filter(pret=self).delete()
            
            # Créer un log d'audit avant la suppression
            from .models import AuditLog
            current_user = getattr(self, '_current_user', None)
            if current_user:
                AuditLog.objects.create(
                    utilisateur=current_user,
                    action='SUPPRESSION',
                    modele='Pret',
                    objet_id=self.id,
                    details={
                        'numero_pret': self.numero_pret,
                        'membre': self.membre.nom_complet,
                        'montant': str(self.montant_demande),
                        'caisse': self.caisse.nom_association,
                        'motif_suppression': 'Prêt rejeté supprimé par admin'
                    },
                    ip_adresse='127.0.0.1'  # Valeur par défaut pour les tests
                )
            
            # Appeler la méthode delete parent
            super().delete(*args, **kwargs)
        else:
            # Pour les autres statuts, interdire la suppression
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f"Impossible de supprimer un prêt avec le statut '{self.statut}'. "
                "Seuls les prêts rejetés peuvent être supprimés."
            )
    
    def __str__(self):
        return f"Prêt {self.numero_pret} - {self.membre.nom_complet}"
    
    def save(self, *args, **kwargs):
        if not self.numero_pret:
            # Génération automatique du numéro de prêt
            self.numero_pret = f"PRT{timezone.now().strftime('%Y%m')}{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    @property
    def montant_restant(self):
        """Calcule le montant restant à rembourser (total à rembourser - montant déjà remboursé)"""
        if self.montant_accord:
            return self.total_a_rembourser - self.montant_rembourse
        return 0
    
    @property
    def total_a_rembourser(self):
        """Calcule le total à rembourser (montant accordé + intérêts)"""
        if self.montant_accord:
            from decimal import Decimal
            montant_principal = self.montant_accord
            montant_interet = montant_principal * (self.taux_interet / Decimal('100'))
            return montant_principal + montant_interet
        return 0
    
    @property
    def montant_interet_calcule(self):
        """Calcule le montant des intérêts"""
        if self.montant_accord:
            from decimal import Decimal
            return self.montant_accord * (self.taux_interet / Decimal('100'))
        return 0
    
    @property
    def est_en_retard(self):
        """Vérifie si le prêt est en retard en se basant sur les échéances"""
        if self.statut in ['EN_COURS', 'EN_RETARD']:
            from django.utils import timezone
            today = timezone.now().date()
            
            # Vérifier s'il y a des échéances en retard
            echeances_en_retard = self.echeances.filter(
                date_echeance__lt=today,
                statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
            ).exists()
            
            return echeances_en_retard
        return False
    
    def calculer_echeances(self):
        """Calcule et crée automatiquement les échéances de remboursement"""
        from decimal import Decimal, ROUND_HALF_UP
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.montant_accord or not self.duree_mois:
            return
        
        # Supprimer les échéances existantes si elles existent
        self.echeances.all().delete()
        
        # Calculer le montant total à rembourser (principal + intérêts)
        montant_principal = self.montant_accord
        montant_interet = self.montant_interet_calcule
        total_a_rembourser = montant_principal + montant_interet
        
        # Calculer le montant de chaque échéance
        montant_echeance = (total_a_rembourser / self.duree_mois).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # Date de début et première échéance (à M+1)
        date_debut = self.date_decaissement.date() if self.date_decaissement else timezone.now().date()
        date_premiere_echeance = self._add_months(date_debut, 1)
        
        # Créer les échéances
        echeances_crees = []
        montant_cumule = Decimal('0.00')
        
        for i in range(self.duree_mois):
            numero_echeance = i + 1
            date_echeance = date_premiere_echeance + timedelta(days=30 * i)
            
            # Pour la dernière échéance, ajuster le montant pour éviter les arrondis
            if numero_echeance == self.duree_mois:
                montant_final = total_a_rembourser - montant_cumule
            else:
                montant_final = montant_echeance
                montant_cumule += montant_echeance
            
            echeance = Echeance.objects.create(
                pret=self,
                numero_echeance=numero_echeance,
                montant_echeance=montant_final,
                date_echeance=date_echeance,
                statut='A_PAYER'
            )
            echeances_crees.append(echeance)
        
        # Mettre à jour les compteurs et la date de fin (dernière échéance)
        self.nombre_echeances = len(echeances_crees)
        self.date_fin_pret = echeances_crees[-1].date_echeance if echeances_crees else None
        self.save(update_fields=['nombre_echeances', 'date_fin_pret'])
        
        return echeances_crees

    def get_or_create_echeances(self):
        """Retourne le queryset d'échéances; si aucune n'existe mais que le prêt est éligible,
        les génère automatiquement (utile pour backfill d'anciens prêts)."""
        qs = self.echeances.all()
        if not qs.exists() and self.statut in ['EN_COURS', 'EN_RETARD'] and self.montant_accord and self.duree_mois:
            try:
                self.calculer_echeances()
                qs = self.echeances.all()
            except Exception:
                return qs
        return qs

    # Utilitaires
    @staticmethod
    def _add_months(source_date, months):
        """Ajoute un nombre de mois en conservant la fin de mois si nécessaire."""
        import calendar
        month = source_date.month - 1 + months
        year = source_date.year + month // 12
        month = month % 12 + 1
        day = min(source_date.day, calendar.monthrange(year, month)[1])
        return source_date.replace(year=year, month=month, day=day)

    def mettre_a_jour_date_fin(self):
        """Calcule et enregistre la date de fin du prêt en fonction de la durée et de la date de décaissement."""
        if self.date_decaissement and self.duree_mois:
            self.date_fin_pret = self._add_months(self.date_decaissement.date(), self.duree_mois)
            self.save(update_fields=['date_fin_pret'])
    
    def get_echeances_en_retard(self):
        """Retourne les échéances en retard"""
        from django.utils import timezone
        today = timezone.now().date()
        
        return self.echeances.filter(
            date_echeance__lt=today,
            statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
        ).order_by('date_echeance')
    
    def get_prochaine_echeance(self):
        """Retourne la prochaine échéance à payer"""
        from django.utils import timezone
        today = timezone.now().date()
        
        return self.echeances.filter(
            date_echeance__gte=today,
            statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
        ).order_by('date_echeance').first()


class Echeance(models.Model):
    """Modèle pour les échéances de remboursement"""
    pret = models.ForeignKey(Pret, on_delete=models.CASCADE, related_name='echeances')
    numero_echeance = models.PositiveIntegerField()
    montant_echeance = models.DecimalField(max_digits=15, decimal_places=2)
    date_echeance = models.DateField()
    montant_paye = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date_paiement = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=[
        ('A_PAYER', 'À payer'),
        ('PARTIELLEMENT_PAYE', 'Partiellement payé'),
        ('PAYE', 'Payé'),
        ('EN_RETARD', 'En retard'),
    ], default='A_PAYER')
    
    class Meta:
        verbose_name = "Échéance"
        verbose_name_plural = "Échéances"
        ordering = ['pret', 'numero_echeance']
        unique_together = ['pret', 'numero_echeance']
    
    def __str__(self):
        return f"Échéance {self.numero_echeance} - Prêt {self.pret.numero_pret}"


class RapportActivite(models.Model):
    """Rapports d'activités liés aux caisses, gérés depuis l'admin."""

    TYPE_CHOICES = [
        ('general', 'Rapport Général'),
        ('financier', 'Rapport Financier'),
        ('prets', 'Rapport des Prêts'),
        ('membres', 'Rapport des Membres'),
        ('echeances', 'Rapport des Échéances'),
    ]

    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('GENERE', 'Généré'),
        ('ECHEC', 'Échec'),
    ]

    caisse = models.ForeignKey('Caisse', on_delete=models.SET_NULL, null=True, blank=True, related_name='rapports')
    type_rapport = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    genere_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rapports_generes')
    date_generation = models.DateTimeField(null=True, blank=True)
    donnees = models.JSONField(default=dict, blank=True)
    fichier_pdf = models.FileField(upload_to='rapports/', null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Rapport d’activité'
        verbose_name_plural = 'Rapports d’activité'
        ordering = ['-date_generation']

    def __str__(self):
        label_caisse = self.caisse.nom_association if self.caisse else 'Toutes Caisses'
        return f"Rapport {self.get_type_rapport_display()} - {label_caisse}"

class MouvementFond(models.Model):
    """Modèle pour les mouvements de fonds des caisses"""
    TYPE_CHOICES = [
        ('ALIMENTATION', 'Alimentation'),
        ('DECAISSEMENT', 'Décaissement'),
        ('REMBOURSEMENT', 'Remboursement'),
        ('FRAIS', 'Frais'),
        ('AUTRE', 'Autre'),
    ]
    
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='mouvements_fonds')
    type_mouvement = models.CharField(max_length=20, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    solde_avant = models.DecimalField(max_digits=15, decimal_places=2)
    solde_apres = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Référence au prêt si applicable
    pret = models.ForeignKey(Pret, on_delete=models.SET_NULL, null=True, blank=True, 
                           related_name='mouvements_fonds')
    
    # Informations de traçabilité
    date_mouvement = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                 related_name='mouvements_fonds_crees')
    description = models.TextField()
    
    class Meta:
        verbose_name = "Mouvement de fond"
        verbose_name_plural = "Mouvements de fonds"
        ordering = ['-date_mouvement']
    
    def __str__(self):
        return f"{self.type_mouvement} - {self.montant} - {self.caisse.nom_association}"


class VirementBancaire(models.Model):
    """Modèle pour les virements bancaires vers les caisses"""
    STATUT_CHOICES = [
        ('DEMANDE', 'Demande'),
        ('EN_COURS', 'En cours'),
        ('EFFECTUE', 'Effectué'),
        ('ECHOUE', 'Échoué'),
        ('ANNULE', 'Annulé'),
    ]
    
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='virements_bancaires')
    numero_compte_cible = models.CharField(max_length=50)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='DEMANDE')
    
    # Informations de traçabilité
    date_demande = models.DateTimeField(auto_now_add=True)
    date_execution = models.DateTimeField(null=True, blank=True)
    reference_bancaire = models.CharField(max_length=100, blank=True)
    
    # Métadonnées
    description = models.TextField()
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Virement bancaire"
        verbose_name_plural = "Virements bancaires"
        ordering = ['-date_demande']
    
    def __str__(self):
        return f"Virement {self.reference_bancaire or self.id} - {self.caisse.nom_association}"


class AuditLog(models.Model):
    """Journal d'audit pour tracer toutes les actions"""
    ACTION_CHOICES = [
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('SUPPRESSION', 'Suppression'),
        ('VALIDATION', 'Validation'),
        ('REJET', 'Rejet'),
        ('NOTIFICATION', 'Notification'),
    ]
    
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Utilisateur")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action")
    modele = models.CharField(max_length=50, verbose_name="Modèle")
    objet_id = models.PositiveIntegerField(verbose_name="ID de l'objet")
    details = models.JSONField(default=dict, verbose_name="Détails")
    date_action = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'action")
    ip_adresse = models.GenericIPAddressField(blank=True, null=True, verbose_name="Adresse IP")
    
    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-date_action']
    
    def __str__(self):
        username = self.utilisateur.username if self.utilisateur else "Utilisateur Anonyme"
        return f"{self.action} - {self.modele} #{self.objet_id} par {username}"


class Notification(models.Model):
    """Système de notifications pour les alertes et communications"""
    TYPE_CHOICES = [
        ('DEMANDE_PRET', 'Demande de prêt'),
        ('VALIDATION_PRET', 'Validation de prêt'),
        ('REJET_PRET', 'Rejet de prêt'),
        ('ATTENTE_PRET', 'Mise en attente de prêt'),
        ('OCTROI_PRET', 'Octroi de prêt'),
        ('ALERTE_FOND', 'Alerte fond insuffisant'),
        ('ALERTE_RETARD', 'Alerte prêt en retard'),
        ('SYSTEME', 'Notification système'),
    ]
    
    STATUT_CHOICES = [
        ('NON_LU', 'Non lu'),
        ('LU', 'Lu'),
        ('TRAITE', 'Traité'),
    ]
    
    destinataire = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Destinataire")
    type_notification = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type")
    titre = models.CharField(max_length=200, verbose_name="Titre")
    message = models.TextField(verbose_name="Message")
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Caisse concernée")
    pret = models.ForeignKey(Pret, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Prêt concerné")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='NON_LU', verbose_name="Statut")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_lecture = models.DateTimeField(null=True, blank=True, verbose_name="Date de lecture")
    date_traitement = models.DateTimeField(null=True, blank=True, verbose_name="Date de traitement")
    lien_action = models.CharField(max_length=200, blank=True, verbose_name="Lien d'action")
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.type_notification} - {self.titre} pour {self.destinataire.username}"
    
    def marquer_comme_lu(self):
        """Marquer la notification comme lue"""
        self.statut = 'LU'
        self.date_lecture = timezone.now()
        self.save()
    
    def marquer_comme_traite(self):
        """Marquer la notification comme traitée"""
        self.statut = 'TRAITE'
        self.date_traitement = timezone.now()
        self.save()


class PresidentGeneral(models.Model):
    """Modèle pour le Président Général de toutes les caisses"""
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenoms = models.CharField(max_length=200, verbose_name="Prénoms")
    numero_carte_electeur = models.CharField(max_length=20, unique=True, verbose_name="Numéro de carte d'électeur")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    adresse = models.TextField(verbose_name="Adresse")
    numero_telephone = models.CharField(max_length=8, verbose_name="Numéro de téléphone")
    photo = models.ImageField(upload_to='photos_president_general/', null=True, blank=True, verbose_name="Photo")
    signature = models.ImageField(upload_to='signatures_president_general/', null=True, blank=True, verbose_name="Signature")
    
    # Informations de gestion
    date_nomination = models.DateTimeField(auto_now_add=True, verbose_name="Date de nomination")
    statut = models.CharField(max_length=20, choices=[
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
    ], default='ACTIF', verbose_name="Statut")
    
    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    class Meta:
        verbose_name = "Président Général"
        verbose_name_plural = "Présidents Généraux"
        ordering = ['-date_nomination']
    
    def __str__(self):
        return f"Président Général: {self.nom} {self.prenoms}"
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Vérifier qu'il n'y a qu'un seul président général actif
        if self.statut == 'ACTIF':
            autres_presidents = PresidentGeneral.objects.filter(statut='ACTIF').exclude(pk=self.pk)
            if autres_presidents.exists():
                raise ValidationError("Il ne peut y avoir qu'un seul Président Général actif à la fois.")


class Parametre(models.Model):
    """Modèle pour les paramètres administratifs et personnels de l'application"""
    
    # Informations de base de l'application
    nom_application = models.CharField(max_length=200, default="CAISSE DE SOLIDARITÉ", verbose_name="Nom de l'application")
    logo = models.ImageField(upload_to='logos/', null=True, blank=True, verbose_name="Logo de l'application")
    description_application = models.TextField(blank=True, verbose_name="Description de l'application")
    version_application = models.CharField(max_length=20, default="1.0.0", verbose_name="Version de l'application")
    
    # Informations de contact
    telephone_principal = models.CharField(max_length=20, blank=True, verbose_name="Téléphone principal")
    telephone_secondaire = models.CharField(max_length=20, blank=True, verbose_name="Téléphone secondaire")
    email_contact = models.EmailField(blank=True, verbose_name="Email de contact")
    site_web = models.URLField(blank=True, verbose_name="Site web")
    
    # Adresse et siège social
    siege_social = models.TextField(blank=True, verbose_name="Siège social")
    adresse_postale = models.CharField(max_length=200, blank=True, verbose_name="Adresse postale")
    boite_postale = models.CharField(max_length=20, blank=True, verbose_name="Boîte postale")
    ville = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    pays = models.CharField(max_length=100, default="Togo", verbose_name="Pays")
    
    # Informations sur le Président Général/PDG
    nom_president_general = models.CharField(max_length=200, blank=True, verbose_name="Nom du Président Général/PDG")
    titre_president_general = models.CharField(max_length=100, default="Président Général", verbose_name="Titre du Président Général")
    signature_president_general = models.ImageField(upload_to='signatures_pdg/', null=True, blank=True, verbose_name="Signature du Président Général")
    
    # Informations sur le personnel
    nom_directeur_technique = models.CharField(max_length=200, blank=True, verbose_name="Nom du Directeur Technique")
    nom_directeur_financier = models.CharField(max_length=200, blank=True, verbose_name="Nom du Directeur Financier")
    nom_directeur_administratif = models.CharField(max_length=200, blank=True, verbose_name="Nom du Directeur Administratif")
    
    # Informations légales et réglementaires
    numero_agrement = models.CharField(max_length=50, blank=True, verbose_name="Numéro d'agrément")
    date_agrement = models.DateField(null=True, blank=True, verbose_name="Date d'agrément")
    autorite_agrement = models.CharField(max_length=200, blank=True, verbose_name="Autorité d'agrément")
    
    # Paramètres système
    devise = models.CharField(max_length=10, default="FCFA", verbose_name="Devise")
    langue_par_defaut = models.CharField(max_length=10, default="fr", verbose_name="Langue par défaut")
    fuseau_horaire = models.CharField(max_length=50, default="Africa/Lome", verbose_name="Fuseau horaire")
    
    # Informations de copyright et mentions légales
    copyright_text = models.CharField(max_length=200, blank=True, verbose_name="Texte de copyright")
    mentions_legales = models.TextField(blank=True, verbose_name="Mentions légales")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    actif = models.BooleanField(default=True, verbose_name="Paramètres actifs")
    
    class Meta:
        verbose_name = "Paramètre"
        verbose_name_plural = "Paramètres"
    
    def __str__(self):
        return f"Paramètres de {self.nom_application}"
    
    @classmethod
    def get_parametres_actifs(cls):
        """Récupère les paramètres actifs (il ne doit y en avoir qu'un seul)"""
        return cls.objects.filter(actif=True).first()


class CaisseGenerale(models.Model):
    """Réserve centrale et vue agrégée du système.

    - solde_reserve: fonds propres de la caisse générale (utilisés pour alimenter les caisses)
    - solde_total_caisses: somme des fonds disponibles de toutes les caisses (synchronisé par signaux)
    - solde_systeme = solde_reserve + solde_total_caisses (propriété)
    """

    nom = models.CharField(max_length=100, default="Caisse Générale", verbose_name="Nom")
    solde_reserve = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Solde de réserve")
    solde_total_caisses = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Somme des caisses")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_mise_a_jour = models.DateTimeField(auto_now=True, verbose_name="Dernière mise à jour")

    class Meta:
        verbose_name = "Caisse Générale"
        verbose_name_plural = "Caisse Générale"

    def __str__(self):
        return f"{self.nom}"

    @property
    def solde_systeme(self):
        return (self.solde_reserve or 0) + (self.solde_total_caisses or 0)

    @classmethod
    def get_instance(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj

    def recalculer_total_caisses(self):
        from django.db.models import Sum
        total = Caisse.objects.aggregate(total=Sum('fond_disponible'))['total'] or 0
        self.solde_total_caisses = total
        self.save(update_fields=['solde_total_caisses', 'date_mise_a_jour'])


class CaisseGeneraleMouvement(models.Model):
    """Mouvements de la caisse générale et opérations d'alimentation des caisses."""

    TYPE_CHOICES = [
        ('ENTREE', 'Entrée (crédit réserve)'),
        ('SORTIE', 'Sortie (débit réserve)'),
        ('ALIMENTATION_CAISSE', "Alimentation d'une caisse"),
    ]

    type_mouvement = models.CharField(max_length=30, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    solde_avant = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    solde_apres = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    caisse_destination = models.ForeignKey('Caisse', on_delete=models.SET_NULL, null=True, blank=True, related_name='alimentations_recuees')
    description = models.TextField(blank=True)
    date_mouvement = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Mouvement caisse générale"
        verbose_name_plural = "Mouvements caisse générale"
        ordering = ['-date_mouvement']

    def __str__(self):
        cible = f" -> {self.caisse_destination.nom_association}" if self.caisse_destination else ""
        return f"{self.type_mouvement} {self.montant}{cible}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Vérifier qu'il n'y a qu'un seul ensemble de paramètres actifs
        if self.actif:
            autres_parametres = Parametre.objects.filter(actif=True).exclude(pk=self.pk)
            if autres_parametres.exists():
                raise ValidationError("Il ne peut y avoir qu'un seul ensemble de paramètres actifs à la fois.")
    
    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'un seul ensemble de paramètres actifs
        if self.actif:
            Parametre.objects.filter(actif=True).exclude(pk=self.pk).update(actif=False)
        super().save(*args, **kwargs)
