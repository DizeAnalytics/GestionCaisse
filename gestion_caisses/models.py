# flake8: noqa
# pylint: skip-file
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportAttributeAccessIssue=false, reportUnknownVariableType=false, reportMissingImports=false
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
import unicodedata
import uuid
import random
import string


def generate_fkm_code_from_name(model_cls, name_source, field_name='code', prefix='FKM', length=4, max_attempts=50):
    """Génère un code unique de la forme FKM + 4 lettres prises au hasard du nom.

    - Les lettres sont extraites du nom (caractères alphabétiques uniquement), en majuscules.
    - Si le nom a moins de 4 lettres distinctes, on complète avec des lettres aléatoires A-Z.
    - On vérifie l'unicité pour le champ `field_name` du `model_cls` si ce champ est unique.
    """
    if not name_source:
        base_letters = []
    else:
        base_letters = [c for c in name_source.upper() if c.isalpha()]

    # Préparer un pool de lettres (au moins 4)
    if len(base_letters) < length:
        base_letters = (base_letters + [random.choice(string.ascii_uppercase) for _ in range(length - len(base_letters))])

    # Tenter plusieurs combinaisons pour trouver une valeur unique si nécessaire
    for _ in range(max_attempts):
        chosen = ''.join(random.choice(base_letters) for _ in range(length))
        candidate = f"{prefix}{chosen}"

        # Vérifier l'unicité uniquement si le champ est unique dans le modèle
        field = model_cls._meta.get_field(field_name)
        if getattr(field, 'unique', False):
            if not model_cls.objects.filter(**{field_name: candidate}).exists():
                return candidate
        else:
            return candidate

    # En dernier recours, ajouter un suffixe numérique
    suffix = random.randint(100, 999)
    return f"{prefix}{''.join(random.choice(base_letters) for _ in range(length))}{suffix}"


def add_months_to_date(source_date, months):
    """Ajoute un nombre de mois à une date en conservant un jour valide."""
    import calendar
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return source_date.replace(year=year, month=month, day=day)


def assert_exercice_ouvert(caisse):
    """Vérifie qu'une caisse a un exercice en cours et non clos à la date du jour.

    Lève ValidationError si aucune activité n'est possible (aucun exercice actif ou exercice clôturé).
    """
    today = timezone.now().date()
    exercice = getattr(caisse, 'exercices', None)
    if exercice is None:
        raise ValidationError({
            'caisse': "Aucun exercice défini pour cette caisse. Veuillez ouvrir un exercice (réservé aux administrateurs)."
        })
    actif = caisse.exercices.filter(statut='EN_COURS').order_by('-date_debut').first()
    if not actif:
        raise ValidationError({
            'caisse': "Aucun exercice en cours pour cette caisse. Les activités sont bloquées jusqu'à ouverture d'un exercice."
        })
    if actif.date_fin and today > actif.date_fin:
        raise ValidationError({
            'caisse': f"Exercice clôturé depuis le {actif.date_fin}. Aucune activité n'est autorisée après la clôture."
        })
    return True


class Region(models.Model):
    """Modèle pour les régions du Togo"""
    nom = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for Region."""
        verbose_name = "Région"
        verbose_name_plural = "Régions"
        ordering = ['nom']
    
    def __str__(self) -> str:
        return self.nom
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_fkm_code_from_name(Region, self.nom)
        super().save(*args, **kwargs)


class Prefecture(models.Model):
    """Modèle pour les préfectures"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='prefectures')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for Prefecture."""
        verbose_name = "Préfecture"
        verbose_name_plural = "Préfectures"
        ordering = ['nom']
        unique_together = ['nom', 'region']
    
    def __str__(self) -> str:
        return f"{self.nom} ({self.region.nom})"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_fkm_code_from_name(Prefecture, self.nom)
        super().save(*args, **kwargs)


class Commune(models.Model):
    """Modèle pour les communes"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    prefecture = models.ForeignKey(Prefecture, on_delete=models.CASCADE, related_name='communes')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for Commune."""
        verbose_name = "Commune"
        verbose_name_plural = "Communes"
        ordering = ['nom']
        unique_together = ['nom', 'prefecture']
    
    def __str__(self) -> str:
        return f"{self.nom} ({self.prefecture.nom})"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_fkm_code_from_name(Commune, self.nom)
        super().save(*args, **kwargs)


class Canton(models.Model):
    """Modèle pour les cantons"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='cantons')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for Canton."""
        verbose_name = "Canton"
        verbose_name_plural = "Cantons"
        ordering = ['nom']
        unique_together = ['nom', 'commune']
    
    def __str__(self) -> str:
        return f"{self.nom} ({self.commune.nom})"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_fkm_code_from_name(Canton, self.nom)
        super().save(*args, **kwargs)


class Village(models.Model):
    """Modèle pour les villages"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    canton = models.ForeignKey(Canton, on_delete=models.CASCADE, related_name='villages')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for Village."""
        verbose_name = "Village"
        verbose_name_plural = "Villages"
        ordering = ['nom']
        unique_together = ['nom', 'canton']
    
    def __str__(self) -> str:
        return f"{self.nom} ({self.canton.nom})"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_fkm_code_from_name(Village, self.nom)
        super().save(*args, **kwargs)


class Quartier(models.Model):
    """Quartier rattaché à un village"""
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    village = models.ForeignKey(Village, on_delete=models.CASCADE, related_name='quartiers')
    description = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Django model metadata for Quartier."""
        verbose_name = "Quartier"
        verbose_name_plural = "Quartiers"
        ordering = ['nom']
        unique_together = ['nom', 'village']

    def __str__(self) -> str:
        return f"{self.nom} ({self.village.nom})"
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_fkm_code_from_name(Quartier, self.nom)
        super().save(*args, **kwargs)

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
    possede_carte_electeur = models.BooleanField(default=True, verbose_name="Possède une carte d'électeur")
    carte_electeur_valide = models.BooleanField(default=False, verbose_name="Carte d'électeur valide")
    numero_carte_electeur = models.CharField(
        max_length=26,
        unique=True,
        help_text="Numéro de carte d'électeur: exactement 26 caractères (A-Z, 0-9, tirets)",
        validators=[
            RegexValidator(
                regex=r'^(?!-)(?!.*--)(?=.*-)[A-Z0-9-]{26}(?<!-)$',
                message="Format invalide. Utiliser exactement 26 caractères (A-Z, 0-9 et '-') sans tiret au début/fin ni doubles tirets."
            )
        ]
    )
    date_naissance = models.DateField()
    adresse = models.TextField()
    indicatif_telephone = models.CharField(
        max_length=5,
        choices=[('+228', 'Togo'), ('+229', 'Bénin'), ('+233', 'Ghana')],
        default='+228',
        help_text="Indicatif du pays du numéro de téléphone"
    )
    numero_telephone = models.CharField(
        max_length=12,
        help_text="Numéro de téléphone (sans indicatif). Longueur contrôlée selon l'indicatif.",
        validators=[
            RegexValidator(regex=r'^[0-9]+$', message='Le numéro de téléphone doit contenir uniquement des chiffres')
        ]
    )
    numero_whatsapp = models.CharField(
        max_length=12,
        null=True,
        blank=True,
        help_text="Numéro WhatsApp (sans indicatif, optionnel). Longueur contrôlée selon l'indicatif.",
        validators=[
            RegexValidator(regex=r'^[0-9]+$', message='Le numéro WhatsApp doit contenir uniquement des chiffres')
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
    quartier = models.ForeignKey('Quartier', on_delete=models.SET_NULL, null=True, blank=True, related_name='agents')
    
    # Informations de gestion
    date_creation = models.DateTimeField(auto_now_add=True)
    date_derniere_activite = models.DateTimeField(auto_now=True)
    
    # Métadonnées
    notes = models.TextField(blank=True)
    
    class Meta:
        """Django model metadata for Agent."""
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
        ordering = ['nom', 'prenoms']
    
    def __str__(self) -> str:
        return f"{self.nom} {self.prenoms} - {self.matricule}"
    
    def save(self, *args, **kwargs):
        """Génère automatiquement le matricule si il n'existe pas"""
        if not self.matricule:
            # Génération robuste du matricule avec contrôle d'unicité
            # Format: AGT + YYYY + 5 chiffres aléatoires (longueur <= 20)
            year_str = timezone.now().strftime('%Y')
            for _ in range(50):
                rand_part = ''.join(random.choice(string.digits) for _ in range(5))
                candidate = f"AGT{year_str}{rand_part}"
                if not Agent.objects.filter(matricule=candidate).exists():
                    self.matricule = candidate
                    break
            if not self.matricule:
                raise ValidationError({
                    'matricule': "Impossible de générer un matricule unique. Veuillez réessayer."
                })
        # Normaliser le numéro de carte
        if self.numero_carte_electeur:
            self.numero_carte_electeur = self.numero_carte_electeur.upper()
        
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

    def clean(self):
        # Longueurs de téléphone selon l'indicatif
        longueur_par_indicatif = {
            '+228': 8,
            '+229': 8,
            '+233': 9,
        }
        attendu = longueur_par_indicatif.get(self.indicatif_telephone)
        if attendu:
            if self.numero_telephone and len(self.numero_telephone) != attendu:
                raise ValidationError({
                    'numero_telephone': f"Le numéro doit avoir {attendu} chiffres pour l'indicatif {self.indicatif_telephone}."
                })
            if self.numero_whatsapp:
                if len(self.numero_whatsapp) != attendu:
                    raise ValidationError({
                        'numero_whatsapp': f"Le numéro WhatsApp doit avoir {attendu} chiffres pour l'indicatif {self.indicatif_telephone}."
                    })
        # Cohérence carte électeur
        if not self.possede_carte_electeur:
            if self.numero_carte_electeur:
                self.numero_carte_electeur = ''
            if self.carte_electeur_valide:
                raise ValidationError({
                    'carte_electeur_valide': "Impossible de marquer valide si l'agent ne possède pas de carte."
                })


class Caisse(models.Model):
    """Modèle principal pour les caisses de femmes"""
    ROLE_CHOICES = [
        ('PRESIDENTE', 'Présidente'),
        ('SECRETAIRE', 'Secrétaire'),
        ('TRESORIERE', 'Trésorière'),
        ('MEMBRE', 'Membre simple'),
    ]
    
    # Code unique automatique
    code = models.CharField(max_length=50, unique=True, editable=False)
    nom_association = models.CharField(max_length=200, unique=True)
    
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
        """Django model metadata for Caisse."""
        verbose_name = "Caisse"
        verbose_name_plural = "Caisses"
        ordering = ['-date_creation']
    
    def __str__(self) -> str:
        return f"{self.code} - {self.nom_association}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Empêcher les doublons de nom (insensible à la casse)
        if self.nom_association:
            qs = Caisse.objects.filter(nom_association__iexact=self.nom_association)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'nom_association': "Une autre caisse possède déjà ce nom. Le nom doit être unique."
                })
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Conserver l'ancien fond_initial et fond_disponible pour ajustement post-save
        old_fond_initial = None
        old_fond_disponible = None
        if not is_new:
            try:
                previous = Caisse.objects.get(pk=self.pk)
                old_fond_initial = previous.fond_initial
                old_fond_disponible = previous.fond_disponible
            except Caisse.DoesNotExist:
                pass

        if not self.code:
            # Générer le code au format: FKM + numéro d'ordre auto-incrémenté (2 chiffres mini) + NOM_CAISSE
            # Exemple: FKM03FEMMENOVISSI
            def normalize_name(value: str) -> str:
                if not value:
                    return ''
                nfkd = unicodedata.normalize('NFKD', value)
                only_letters = ''.join(c for c in nfkd if c.isalpha())
                return only_letters.upper()

            base_name = normalize_name(self.nom_association)

            # Déterminer le prochain numéro d'ordre, avec gestion de collisions potentielles
            # On part sur count+1 puis on incrémente jusqu'à unicité si besoin
            order_num = Caisse.objects.count() + 1
            while True:
                order_str = f"{order_num:02d}"
                candidate = f"FKM{order_str}{base_name}"
                if not Caisse.objects.filter(code=candidate).exists():
                    self.code = candidate
                    break
                order_num += 1
        super().save(*args, **kwargs)
        
        # Synchronisation des fonds
        if is_new:
            # A la création, si fond initial > 0 alors solde disponible = fond initial
            if self.fond_initial > 0:
                self.fond_disponible = self.fond_initial
                super().save(update_fields=['fond_disponible'])
        else:
            # En modification, si le fond_initial a changé, ajuster le fond_disponible par le delta
            if old_fond_initial is not None and self.fond_initial != old_fond_initial:
                delta = self.fond_initial - old_fond_initial
                if old_fond_disponible is None:
                    old_fond_disponible = self.fond_disponible
                self.fond_disponible = (old_fond_disponible or 0) + delta
                super().save(update_fields=['fond_disponible'])
    
    @property
    def nombre_membres(self):
        return self.membres.filter(statut='ACTIF').count()
    
    @property
    def nombre_prets_actifs(self):
        return self.prets.filter(statut='EN_COURS').count()
    
    @property
    def solde_disponible(self):
        # Nouvelle logique: Solde Disponible = Fond initial + Fond disponible
        return (self.fond_initial or 0) + (self.fond_disponible or 0)
    
    @property
    def solde_disponible_depenses(self):
        """
        Retourne le solde disponible des dépenses basé uniquement sur les cotisations.
        
        Solde Dépenses = Total Solidarité + Total Pénalités
        """
        # Total des frais de solidarité de toutes les cotisations de la caisse
        total_solidarite = self.cotisations.aggregate(
            total=Sum('frais_solidarite')
        )['total'] or 0
        # Total des pénalités
        total_penalites = self.cotisations.aggregate(
            total=Sum('penalite_emprunt_retard')
        )['total'] or 0
        # Total des dépenses enregistrées
        total_depenses = self.depenses.aggregate(
            total=Sum('montantdepense')
        )['total'] or 0

        return (total_solidarite + total_penalites - total_depenses)
    
    @property
    def total_frais_solidarite(self):
        """Total des frais de solidarité collectés"""
        return self.cotisations.aggregate(
            total=Sum('frais_solidarite')
        )['total'] or 0
    
    @property
    def total_frais_penalites(self):
        """Total des frais de pénalités collectés"""
        return self.cotisations.aggregate(
            total=Sum('penalite_emprunt_retard')
        )['total'] or 0
    
    @property
    def total_depenses_approuvees(self):
        """Total des dépenses approuvées et terminées"""
        return self.depenses.filter(
            statut__in=['APPROUVEE', 'TERMINEE']
        ).aggregate(
            total=Sum('montant')
        )['total'] or 0
    
    @property
    def total_depenses_en_cours(self):
        """Total des dépenses en cours d'approbation"""
        return self.depenses.filter(
            statut='EN_COURS'
        ).aggregate(
            total=Sum('montant')
        )['total'] or 0


class ExerciceCaisse(models.Model):
    """Période d'exercice pour une caisse (durée standard: 10 mois).

    - Seuls les administrateurs peuvent ouvrir un exercice (côté API/admin).
    - Une caisse ne peut pas avoir deux exercices en cours.
    - Après la date de fin, les activités (créations/modifications financières) sont bloquées.
    """
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('CLOTURE', 'Clôturé'),
    ]

    caisse = models.ForeignKey('Caisse', on_delete=models.CASCADE, related_name='exercices')
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True, help_text="Calcul automatique: date_debut + 10 mois")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    notes = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exercice de caisse"
        verbose_name_plural = "Exercices de caisse"
        ordering = ['-date_debut', '-date_creation']
        indexes = [
            models.Index(fields=['caisse']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_debut']),
        ]

    def __str__(self):
        fin_txt = self.date_fin.strftime('%d/%m/%Y') if self.date_fin else 'N/A'
        return f"{self.caisse.nom_association} - Exercice du {self.date_debut.strftime('%d/%m/%Y')} au {fin_txt} ({self.get_statut_display()})"

    @property
    def est_actif(self):
        today = timezone.now().date()
        if self.statut != 'EN_COURS':
            return False
        if self.date_fin and today > self.date_fin:
            return False
        return True

    def clean(self):
        from django.core.exceptions import ValidationError
        # Un seul exercice EN_COURS par caisse
        if self.statut == 'EN_COURS':
            qs = ExerciceCaisse.objects.filter(caisse=self.caisse, statut='EN_COURS')
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'statut': "Cette caisse a déjà un exercice en cours. Clôturez-le avant d'en ouvrir un nouveau."
                })
        # Calculer date_fin si manquante
        if not self.date_fin and self.date_debut:
            self.date_fin = add_months_to_date(self.date_debut, 10)

    def save(self, *args, **kwargs):
        # Assurer la date_fin
        if not self.date_fin and self.date_debut:
            self.date_fin = add_months_to_date(self.date_debut, 10)
        super().save(*args, **kwargs)


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
    
    # Identification carte électeur
    possede_carte_electeur = models.BooleanField(default=True, verbose_name="Possède une carte d'électeur")
    carte_electeur_valide = models.BooleanField(default=False, verbose_name="Carte d'électeur valide")
    numero_carte_electeur = models.CharField(
        max_length=26,
        help_text="Numéro de carte d'électeur: exactement 26 caractères (A-Z, 0-9, tirets)",
        validators=[
            RegexValidator(
                regex=r'^(?!-)(?!.*--)(?=.*-)[A-Z0-9-]{26}(?<!-)$',
                message="Format invalide. Utiliser exactement 26 caractères (A-Z, 0-9 et '-') sans tiret au début/fin ni doubles tirets."
            )
        ]
    )
    
    # Informations personnelles
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=200)
    date_naissance = models.DateField()
    adresse = models.TextField()
    indicatif_telephone = models.CharField(
        max_length=5,
        choices=[('+228', 'Togo'), ('+229', 'Bénin'), ('+233', 'Ghana')],
        default='+228',
        help_text="Indicatif du pays du numéro de téléphone"
    )
    numero_telephone = models.CharField(
        max_length=12,
        help_text="Numéro de téléphone (sans indicatif). Longueur contrôlée selon l'indicatif.",
        validators=[
            RegexValidator(regex=r'^[0-9]+$', message='Le numéro de téléphone doit contenir uniquement des chiffres')
        ]
    )
    numero_whatsapp = models.CharField(
        max_length=12,
        null=True,
        blank=True,
        help_text="Numéro WhatsApp (sans indicatif, optionnel). Longueur contrôlée selon l'indicatif.",
        validators=[
            RegexValidator(regex=r'^[0-9]+$', message='Le numéro WhatsApp doit contenir uniquement des chiffres')
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
    
    # Localisation et appartenance
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='membres')
    quartier = models.ForeignKey(Quartier, on_delete=models.SET_NULL, null=True, blank=True, related_name='membres')

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
        # Normaliser le numéro de carte
        if self.numero_carte_electeur:
            self.numero_carte_electeur = self.numero_carte_electeur.upper()
        # Longueurs de téléphone selon l'indicatif
        longueur_par_indicatif = {
            '+228': 8,   # Togo
            '+229': 8,   # Bénin
            '+233': 9,   # Ghana (format international sans le 0 initial)
        }
        attendu = longueur_par_indicatif.get(self.indicatif_telephone)
        if attendu:
            if self.numero_telephone and len(self.numero_telephone) != attendu:
                raise ValidationError({
                    'numero_telephone': f"Le numéro doit avoir {attendu} chiffres pour l'indicatif {self.indicatif_telephone}."
                })
            if self.numero_whatsapp:
                if len(self.numero_whatsapp) != attendu:
                    raise ValidationError({
                        'numero_whatsapp': f"Le numéro WhatsApp doit avoir {attendu} chiffres pour l'indicatif {self.indicatif_telephone}."
                    })
        # Cohérence carte électeur
        if not self.possede_carte_electeur:
            # Si pas de carte, le numéro peut être vide
            if self.numero_carte_electeur:
                self.numero_carte_electeur = ''
            if self.carte_electeur_valide:
                raise ValidationError({
                    'carte_electeur_valide': "Impossible de marquer valide si le membre ne possède pas de carte."
                })
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}"

    def nombre_mois_cotises(self):
        """Retourne le nombre de mois distincts pour lesquels ce membre a cotisé dans sa caisse."""
        try:
            from django.db.models.functions import TruncMonth
            return self.cotisations.annotate(mois=TruncMonth('date_cotisation')).values('mois').distinct().count()
        except Exception:
            # Si pas de table cotisations ou autre erreur, considérer 0
            return 0

    def est_eligible_pret_selon_cotisations(self, minimum_mois=3):
        """Vérifie l'éligibilité au prêt basée sur les cotisations (par défaut 3 mois distincts)."""
        return self.nombre_mois_cotises() >= minimum_mois

    def total_cotisations(self):
        """Somme totale des cotisations du membre (toutes composantes confondues)."""
        try:
            from django.db.models import Sum
            return self.cotisations.aggregate(total=Sum('montant_total'))['total'] or 0
        except Exception:
            return 0


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
        """Surcharge de la méthode delete pour gérer la suppression des prêts rejetés et bloqués"""
        # Si le prêt est rejeté ou bloqué, on peut le supprimer
        if self.statut in ['REJETE', 'BLOQUE']:
            # Supprimer d'abord les notifications liées
            Notification.objects.filter(pret=self).delete()
            
            # Supprimer les échéances liées
            Echeance.objects.filter(pret=self).delete()
            
            # Supprimer les mouvements de fonds liés
            MouvementFond.objects.filter(pret=self).delete()
            
            # Créer un log d'audit avant la suppression
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
                        'motif_suppression': f'Prêt {self.statut.lower()} supprimé par admin'
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
                "Seuls les prêts rejetés et bloqués peuvent être supprimés."
            )
    
    def __str__(self) -> str:
        return f"Prêt {self.numero_pret} - {self.membre.nom_complet}"
    
    def clean(self):
        """Validation personnalisée pour les prêts"""
        from django.core.exceptions import ValidationError
        
        # Bloquer si aucun exercice actif pour la caisse
        if self.caisse_id:
            assert_exercice_ouvert(self.caisse)

        # Vérifier que le membre n'a pas déjà un prêt ouvert (exclure les prêts remboursés et rejetés)
        if self.pk is None:  # Nouveau prêt
            prets_ouverts = Pret.objects.filter(
                membre=self.membre,
                statut__in=['EN_ATTENTE', 'EN_ATTENTE_ADMIN', 'VALIDE', 'EN_COURS', 'EN_RETARD', 'BLOQUE']
            ).exclude(pk=self.pk)
            
            if prets_ouverts.exists():
                pret_existant = prets_ouverts.first()
                raise ValidationError({
                    'membre': f"Le membre {self.membre.nom_complet} a déjà un prêt en cours (statut: {pret_existant.get_statut_display()}). "
                              "Il doit clôturer ce prêt avant d'en créer un nouveau. "
                              "Les prêts remboursés permettent de faire un nouveau prêt."
                })
        
        # Vérifier que le montant demandé est positif
        if self.montant_demande <= 0:
            raise ValidationError({
                'montant_demande': 'Le montant demandé doit être strictement positif.'
            })
        
        # Vérifier que la durée est positive
        if self.duree_mois <= 0:
            raise ValidationError({
                'duree_mois': 'La durée du prêt doit être strictement positive.'
            })

        # Règle métier: éligibilité conditionnée au total de cotisations >= 3000 FCFA
        # Appliquée en création uniquement.
        if self.pk is None and self.membre_id and self.caisse_id:
            try:
                total_cot = self.membre.total_cotisations() if hasattr(self.membre, 'total_cotisations') else 0
                if total_cot < 3000:
                    raise ValidationError({
                        'membre': "Le membre n'est pas éligible: au moins 3000 FCFA de cotisations requis avant de demander un prêt."
                    })
            except Exception:
                # En cas d'erreur d'accès aux cotisations, refuser par prudence
                raise ValidationError({
                    'membre': "Impossible de vérifier les cotisations du membre. Veuillez réessayer."
                })
    
    def save(self, *args, **kwargs):
        if not self.numero_pret:
            # Génération automatique du numéro de prêt
            self.numero_pret = f"PRT{timezone.now().strftime('%Y%m')}{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    @property
    def montant_restant(self):
        """Calcule le montant restant total (principal + intérêts restants).

        On considère:
        - total à rembourser = principal + intérêts calculés
        - total déjà payé = somme des mouvements REMBOURSEMENT (principal + intérêts)
          Si pour une raison quelconque des mouvements ne sont pas disponibles,
          on retombe sur le cumul principal (montant_rembourse).
        """
        if not self.montant_accord:
            return 0
        from decimal import Decimal
        total = self.total_a_rembourser or Decimal('0')
        total_paye = self.mouvements_fonds.filter(type_mouvement='REMBOURSEMENT').aggregate(models.Sum('montant'))['montant__sum'] or Decimal('0')
        # À défaut de mouvements, se baser sur le principal remboursé
        if total_paye <= 0:
            total_paye = self.montant_rembourse or Decimal('0')
        restant = total - total_paye
        return restant if restant > 0 else Decimal('0')
    
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
        today = timezone.now().date()
        
        return self.echeances.filter(
            date_echeance__lt=today,
            statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
        ).order_by('date_echeance')
    
    def get_prochaine_echeance(self):
        """Retourne la prochaine échéance à payer"""
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
        """Django model metadata for Echeance."""
        verbose_name = "Échéance"
        verbose_name_plural = "Échéances"
        ordering = ['pret', 'numero_echeance']
        unique_together = ['pret', 'numero_echeance']
    
    def __str__(self):
        return f"Échéance {self.numero_echeance} - Prêt {self.pret.numero_pret}"


class MouvementFond(models.Model):
    """Modèle pour les mouvements de fonds des caisses"""
    TYPE_CHOICES = [
        ('ALIMENTATION', 'Alimentation'),
        ('DECAISSEMENT', 'Décaissement'),
        ('REMBOURSEMENT', 'Remboursement'),
        ('FRAIS', 'Frais'),
        ('AUTRE', 'Autre'),
        ('TRANSFERT_VERS_CAISSE', 'Transfert vers une autre caisse'),
        ('TRANSFERT_VERS_GENERALE', 'Transfert vers la caisse générale'),
        ('RECEPTION_CAISSE', 'Réception d\'un transfert d\'une autre caisse'),
        ('RECEPTION_GENERALE', 'Réception d\'un transfert de la caisse générale'),
    ]
    
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='mouvements_fonds')
    type_mouvement = models.CharField(max_length=30, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    solde_avant = models.DecimalField(max_digits=15, decimal_places=2)
    solde_apres = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Référence au prêt si applicable
    pret = models.ForeignKey(Pret, on_delete=models.SET_NULL, null=True, blank=True, 
                           related_name='mouvements_fonds')
    
    # Référence à la caisse source/destination pour les transferts
    caisse_source = models.ForeignKey('Caisse', on_delete=models.SET_NULL, null=True, blank=True, 
                                    related_name='mouvements_transferts_envoyes')
    caisse_destination = models.ForeignKey('Caisse', on_delete=models.SET_NULL, null=True, blank=True, 
                                         related_name='mouvements_transferts_recus')
    
    # Informations de traçabilité
    date_mouvement = models.DateTimeField(auto_now_add=True)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                 related_name='mouvements_fonds_crees')
    description = models.TextField()
    
    class Meta:
        """Django model metadata for MouvementFond."""
        verbose_name = "Mouvement de fond"
        verbose_name_plural = "Mouvements de fonds"
        ordering = ['-date_mouvement']
    
    def __str__(self):
        if self.type_mouvement in ['TRANSFERT_VERS_CAISSE', 'TRANSFERT_VERS_GENERALE']:
            return f"{self.type_mouvement} - {self.montant} - {self.caisse.nom_association}"
        elif self.type_mouvement in ['RECEPTION_CAISSE', 'RECEPTION_GENERALE']:
            return f"{self.type_mouvement} - {self.montant} - {self.caisse.nom_association}"
        else:
            return f"{self.type_mouvement} - {self.montant} - {self.caisse.nom_association}"
    
    def clean(self):
        """Validation personnalisée pour les mouvements de fonds"""
        
        # Bloquer si aucun exercice actif pour la caisse
        if self.caisse_id:
            assert_exercice_ouvert(self.caisse)

        # Vérifier que le montant est positif
        if self.montant <= 0:
            raise ValidationError("Le montant doit être strictement positif.")
        
        # Validation spécifique pour les transferts
        if self.type_mouvement == 'TRANSFERT_VERS_CAISSE':
            if not self.caisse_destination:
                raise ValidationError("Une caisse de destination est requise pour un transfert vers une autre caisse.")
            if self.caisse_destination == self.caisse:
                raise ValidationError("Une caisse ne peut pas se transférer de l'argent à elle-même.")
            # Vérifier que la caisse source a suffisamment de fonds
            if self.caisse.fond_disponible < self.montant:
                raise ValidationError(
                    f"Fonds insuffisants. La caisse {self.caisse.nom_association} dispose de {self.caisse.fond_disponible} FCFA, "
                    f"mais {self.montant} FCFA sont demandés pour le transfert."
                )
        
        elif self.type_mouvement == 'TRANSFERT_VERS_GENERALE':
            # Vérifier que la caisse source a suffisamment de fonds
            if self.caisse.fond_disponible < self.montant:
                raise ValidationError(
                    f"Fonds insuffisants. La caisse {self.caisse.nom_association} dispose de {self.caisse.fond_disponible} FCFA, "
                    f"mais {self.montant} FCFA sont demandés pour le transfert vers la caisse générale."
                )
        
        elif self.type_mouvement in ['RECEPTION_CAISSE', 'RECEPTION_GENERALE']:
            if not self.caisse_source:
                raise ValidationError("Une caisse source est requise pour un mouvement de réception.")
    
    def save(self, *args, **kwargs):
        """Sauvegarde avec calcul automatique des soldes"""
        # Calculer les soldes avant et après si pas déjà définis
        if not self.solde_avant:
            self.solde_avant = self.caisse.fond_disponible
        
        # Calculer le solde après en fonction du type de mouvement
        if self.type_mouvement in ['ALIMENTATION', 'REMBOURSEMENT', 'RECEPTION_CAISSE', 'RECEPTION_GENERALE']:
            self.solde_apres = self.solde_avant + self.montant
        elif self.type_mouvement in ['DECAISSEMENT', 'FRAIS', 'TRANSFERT_VERS_CAISSE', 'TRANSFERT_VERS_GENERALE']:
            self.solde_apres = self.solde_avant - self.montant
        else:
            # Autres types: par défaut on soustrait
            self.solde_apres = self.solde_avant - self.montant
        
        super().save(*args, **kwargs)


class SeanceReunion(models.Model):
    """Séance de réunion d'une caisse (pour regrouper les cotisations par séance)."""
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='seances')
    date_seance = models.DateField()
    titre = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Django model metadata for SeanceReunion."""
        verbose_name = "Séance de réunion"
        verbose_name_plural = "Séances de réunion"
        ordering = ['-date_seance', '-date_creation']
        unique_together = ['caisse', 'date_seance', 'titre']

    def __str__(self):
        lib = self.titre or self.date_seance.strftime('%d/%m/%Y')
        return f"{self.caisse.nom_association} - {lib}"


class Cotisation(models.Model):
    """Cotisation d'un membre lors d'une séance de réunion.

    Décomposée en:
    - prix_tempon
    - frais_solidarite
    - frais_fondation
    - penalite_emprunt_retard (pénalité appliquée aux retardataires sur emprunt)
    """
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='cotisations')
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='cotisations')
    seance = models.ForeignKey(SeanceReunion, on_delete=models.CASCADE, related_name='cotisations')
    date_cotisation = models.DateTimeField(auto_now_add=True)

    prix_tempon = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frais_solidarite = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frais_fondation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalite_emprunt_retard = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        """Django model metadata for Cotisation."""
        verbose_name = "Cotisation"
        verbose_name_plural = "Cotisations"
        ordering = ['-date_cotisation']
        indexes = [
            models.Index(fields=['caisse', 'membre']),
            models.Index(fields=['date_cotisation']),
        ]

    def __str__(self):
        return f"Cotisation {self.membre.nom_complet} - {self.caisse.nom_association} ({self.montant_total} FCFA)"

    def clean(self):
        # Bloquer si aucun exercice actif pour la caisse
        if self.caisse_id:
            assert_exercice_ouvert(self.caisse)
        if self.membre.caisse_id != self.caisse_id:
            raise ValidationError("Le membre doit appartenir à la caisse de la cotisation.")
        if self.seance.caisse_id != self.caisse_id:
            raise ValidationError("La séance doit appartenir à la même caisse que la cotisation.")
        for field in ['prix_tempon', 'frais_solidarite', 'frais_fondation', 'penalite_emprunt_retard']:
            if getattr(self, field) is None:
                setattr(self, field, 0)
            if getattr(self, field) < 0:
                raise ValidationError("Les montants des composantes doivent être positifs ou nuls.")

    def save(self, *args, **kwargs):
        # Valider via clean() pour bloquer toute création sans exercice actif (appelé aussi via API non-admin)
        try:
            self.full_clean()
        except Exception:
            # Relever l'erreur telle quelle
            raise
        # Calculer le total
        from decimal import Decimal
        self.montant_total = (
            (self.prix_tempon or 0) +
            (self.frais_solidarite or 0) +
            (self.frais_fondation or 0) +
            (self.penalite_emprunt_retard or 0)
        )

        is_new = self.pk is None
        super().save(*args, **kwargs)

        # A la création, créditer la caisse et tracer le mouvement
        if is_new and self.montant_total and self.caisse_id:
            solde_avant = self.caisse.fond_disponible
            self.caisse.fond_disponible = solde_avant + self.montant_total
            self.caisse.save(update_fields=['fond_disponible'])

            MouvementFond.objects.create(
                caisse=self.caisse,
                type_mouvement='ALIMENTATION',
                montant=self.montant_total,
                solde_avant=solde_avant,
                solde_apres=self.caisse.fond_disponible,
                description=f"Cotisation séance {self.seance.date_seance} de {self.membre.nom_complet}",
                utilisateur=self.utilisateur
            )

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
        """Django model metadata for VirementBancaire."""
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
        """Django model metadata for AuditLog."""
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
        """Django model metadata for Notification."""
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
        """Django model metadata for PresidentGeneral."""
        verbose_name = "Président Général"
        verbose_name_plural = "Présidents Généraux"
        ordering = ['-date_nomination']
    
    def __str__(self):
        return f"Président Général: {self.nom} {self.prenoms}"
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenoms}"
    
    def clean(self):
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
        """Django model metadata for Parametre."""
        verbose_name = "Paramètre"
        verbose_name_plural = "Paramètres"
    
    def __str__(self):
        return f"Paramètres de {self.nom_application}"
    
    @classmethod
    def get_parametres_actifs(cls):
        """Récupère les paramètres actifs (il ne doit y en avoir qu'un seul)"""
        return cls.objects.filter(actif=True).first()


class AdminDashboard(models.Model):
    """Modèle pour le dashboard d'administration"""
    nom = models.CharField(max_length=100, default="Dashboard Administrateur")
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for AdminDashboard."""
        verbose_name = "Dashboard Administrateur"
        verbose_name_plural = "Dashboards Administrateur"
    
    def __str__(self):
        return f"{self.nom} - {self.date_creation.strftime('%d/%m/%Y')}"


class TransfertCaisse(models.Model):
    """Modèle pour gérer les transferts de fonds entre caisses"""
    
    TYPE_CHOICES = [
        ('CAISSE_VERS_CAISSE', 'Transfert d\'une caisse vers une autre caisse'),
        ('CAISSE_VERS_GENERALE', 'Transfert d\'une caisse vers la caisse générale'),
        ('GENERALE_VERS_CAISSE', 'Transfert de la caisse générale vers une caisse'),
    ]
    
    type_transfert = models.CharField(max_length=30, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Caisse source (qui envoie l'argent)
    # Devient optionnelle pour les transferts 'GENERALE_VERS_CAISSE' où la source est la caisse générale
    caisse_source = models.ForeignKey(Caisse, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='transferts_envoyes', verbose_name="Caisse source")
    
    # Caisse destination (qui reçoit l'argent)
    caisse_destination = models.ForeignKey(Caisse, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='transferts_recus', verbose_name="Caisse destination")
    
    # Informations de traçabilité
    date_transfert = models.DateTimeField(auto_now_add=True, verbose_name="Date du transfert")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Utilisateur responsable")
    description = models.TextField(blank=True, verbose_name="Description du transfert")
    
    # Statut du transfert
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Validé'),
        ('ANNULE', 'Annulé'),
        ('ERREUR', 'Erreur'),
    ]
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    # Référence aux mouvements de fonds créés
    mouvement_source = models.ForeignKey(MouvementFond, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='transfert_source', verbose_name="Mouvement source")
    mouvement_destination = models.ForeignKey(MouvementFond, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='transfert_destination', verbose_name="Mouvement destination")
    
    class Meta:
        """Django model metadata for TransfertCaisse."""
        verbose_name = "Transfert entre caisses"
        verbose_name_plural = "Transferts entre caisses"
        ordering = ['-date_transfert']
    
    def __str__(self):
        if self.type_transfert == 'CAISSE_VERS_CAISSE':
            return f"Transfert {self.caisse_source.nom_association} → {self.caisse_destination.nom_association} ({self.montant} FCFA)"
        elif self.type_transfert == 'CAISSE_VERS_GENERALE':
            return f"Transfert {self.caisse_source.nom_association} → Caisse Générale ({self.montant} FCFA)"
        else:
            return f"Transfert Caisse Générale → {self.caisse_destination.nom_association} ({self.montant} FCFA)"
    
    def clean(self):
        """Validation personnalisée pour les transferts"""
        from django.core.exceptions import ValidationError
        
        # Vérifier que le montant est positif
        if self.montant <= 0:
            raise ValidationError("Le montant doit être strictement positif.")
        
        # Validation selon le type de transfert
        if self.type_transfert == 'CAISSE_VERS_CAISSE':
            if not self.caisse_destination:
                raise ValidationError("Une caisse de destination est requise pour un transfert entre caisses.")
            if self.caisse_source == self.caisse_destination:
                raise ValidationError("Une caisse ne peut pas se transférer de l'argent à elle-même.")
            # Vérifier que la caisse source a suffisamment de fonds
            if self.caisse_source.fond_disponible < self.montant:
                raise ValidationError(
                    f"Fonds insuffisants. La caisse {self.caisse_source.nom_association} dispose de {self.caisse_source.fond_disponible} FCFA, "
                    f"mais {self.montant} FCFA sont demandés pour le transfert."
                )
        
        elif self.type_transfert == 'CAISSE_VERS_GENERALE':
            # Vérifier que la caisse source a suffisamment de fonds
            if self.caisse_source.fond_disponible < self.montant:
                raise ValidationError(
                    f"Fonds insuffisants. La caisse {self.caisse_source.nom_association} dispose de {self.caisse_source.fond_disponible} FCFA, "
                    f"mais {self.montant} FCFA sont demandés pour le transfert vers la caisse générale."
                )
        
        elif self.type_transfert == 'GENERALE_VERS_CAISSE':
            if not self.caisse_destination:
                raise ValidationError("Une caisse de destination est requise pour un transfert de la caisse générale.")
            # Vérifier que la caisse générale a suffisamment de fonds
            caisse_generale = CaisseGenerale.get_instance()
            if caisse_generale.solde_reserve < self.montant:
                raise ValidationError(
                    f"Fonds insuffisants. La caisse générale dispose de {caisse_generale.solde_reserve} FCFA, "
                    f"mais {self.montant} FCFA sont demandés pour le transfert."
                )
    
    def executer_transfert(self):
        """Exécute le transfert en créant les mouvements de fonds appropriés"""
        from django.core.exceptions import ValidationError
        
        # Valider le transfert avant exécution
        self.clean()
        
        try:
            if self.type_transfert == 'CAISSE_VERS_CAISSE':
                # Créer le mouvement de débit pour la caisse source
                mouvement_source = MouvementFond.objects.create(
                    caisse=self.caisse_source,
                    type_mouvement='TRANSFERT_VERS_CAISSE',
                    montant=self.montant,
                    caisse_destination=self.caisse_destination,
                    description=f"Transfert vers {self.caisse_destination.nom_association}",
                    utilisateur=self.utilisateur
                )
                
                # Créer le mouvement de crédit pour la caisse destination
                mouvement_destination = MouvementFond.objects.create(
                    caisse=self.caisse_destination,
                    type_mouvement='RECEPTION_CAISSE',
                    montant=self.montant,
                    caisse_source=self.caisse_source,
                    description=f"Transfert reçu de {self.caisse_source.nom_association}",
                    utilisateur=self.utilisateur
                )
                
                # Mettre à jour les soldes des caisses
                self.caisse_source.fond_disponible -= self.montant
                self.caisse_source.save()
                
                self.caisse_destination.fond_disponible += self.montant
                self.caisse_destination.save()
                
                # Lier les mouvements au transfert
                self.mouvement_source = mouvement_source
                self.mouvement_destination = mouvement_destination
                
            elif self.type_transfert == 'CAISSE_VERS_GENERALE':
                # Créer le mouvement de débit pour la caisse source
                mouvement_source = MouvementFond.objects.create(
                    caisse=self.caisse_source,
                    type_mouvement='TRANSFERT_VERS_GENERALE',
                    montant=self.montant,
                    description="Transfert vers la caisse générale",
                    utilisateur=self.utilisateur
                )
                
                # Créditer la caisse générale
                caisse_generale = CaisseGenerale.get_instance()
                caisse_generale.solde_reserve += self.montant
                caisse_generale.save()
                
                # Créer un mouvement pour la caisse générale
                mouvement_destination = CaisseGeneraleMouvement.objects.create(
                    type_mouvement='ENTREE',
                    montant=self.montant,
                    description=f"Transfert reçu de {self.caisse_source.nom_association}",
                    utilisateur=self.utilisateur
                )
                
                # Mettre à jour le solde de la caisse source
                self.caisse_source.fond_disponible -= self.montant
                self.caisse_source.save()
                
                # Lier le mouvement source au transfert
                self.mouvement_source = mouvement_source
                
            elif self.type_transfert == 'GENERALE_VERS_CAISSE':
                # Débiter la caisse générale
                caisse_generale = CaisseGenerale.get_instance()
                caisse_generale.solde_reserve -= self.montant
                caisse_generale.save()
                
                # Créer un mouvement pour la caisse générale
                mouvement_source = CaisseGeneraleMouvement.objects.create(
                    type_mouvement='SORTIE',
                    montant=self.montant,
                    caisse_destination=self.caisse_destination,
                    description=f"Transfert vers {self.caisse_destination.nom_association}",
                    utilisateur=self.utilisateur
                )
                
                # Créer le mouvement de crédit pour la caisse destination
                mouvement_destination = MouvementFond.objects.create(
                    caisse=self.caisse_destination,
                    type_mouvement='RECEPTION_GENERALE',
                    montant=self.montant,
                    description="Transfert reçu de la caisse générale",
                    utilisateur=self.utilisateur
                )
                
                # Mettre à jour le solde de la caisse destination
                self.caisse_destination.fond_disponible += self.montant
                self.caisse_destination.save()
                
                # Lier les mouvements au transfert
                self.mouvement_source = mouvement_source
                self.mouvement_destination = mouvement_destination
            
            # Marquer le transfert comme validé
            self.statut = 'VALIDE'
            self.save()
            
            # Synchroniser la caisse générale
            try:
                caisse_generale = CaisseGenerale.get_instance()
                caisse_generale.recalculer_total_caisses()
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            self.statut = 'ERREUR'
            self.save()
            raise ValidationError(f"Erreur lors de l'exécution du transfert: {str(e)}")
    
    def annuler_transfert(self):
        """Annule un transfert validé en inversant les mouvements"""
        if self.statut != 'VALIDE':
            raise ValidationError("Seuls les transferts validés peuvent être annulés.")
        
        try:
            # Logique d'annulation selon le type de transfert
            # (À implémenter selon les besoins métier)
            self.statut = 'ANNULE'
            self.save()
            return True
        except Exception as e:
            raise ValidationError(f"Erreur lors de l'annulation du transfert: {str(e)}")


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
        """Django model metadata for CaisseGenerale."""
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
        """Django model metadata for CaisseGeneraleMouvement."""
        verbose_name = "Mouvement caisse générale"
        verbose_name_plural = "Mouvements caisse générale"
        ordering = ['-date_mouvement']

    def __str__(self):
        cible = f" -> {self.caisse_destination.nom_association}" if self.caisse_destination else ""
        return f"{self.type_mouvement} {self.montant}{cible}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Validation spécifique aux mouvements de caisse générale
        if self.montant <= 0:
            raise ValidationError("Le montant doit être strictement positif.")
        
        if self.type_mouvement == 'ALIMENTATION_CAISSE' and not self.caisse_destination:
            raise ValidationError("Une caisse de destination est requise pour l'alimentation d'une caisse.")
        
        # Vérifier que la caisse générale a suffisamment de fonds pour les opérations de débit
        if self.type_mouvement in ['SORTIE', 'ALIMENTATION_CAISSE']:
            caisse_generale = CaisseGenerale.get_instance()
            if caisse_generale.solde_reserve < self.montant:
                raise ValidationError(
                    f"Fonds insuffisants. La caisse générale dispose de {caisse_generale.solde_reserve} FCFA, "
                    f"mais {self.montant} FCFA sont demandés. "
                    f"Solde disponible: {caisse_generale.solde_reserve} FCFA"
                )
    
    def save(self, *args, **kwargs):
        # Déterminer si c'est une création (pour éviter les doubles effets lors d'updates)
        is_new = self.pk is None
        
        # Calculer les soldes avant et après si pas déjà définis
        if not self.solde_avant:
            caisse_generale = CaisseGenerale.get_instance()
            self.solde_avant = caisse_generale.solde_reserve
        
        # Calculer le solde après
        if self.type_mouvement == 'ENTREE':
            self.solde_apres = self.solde_avant + self.montant
        elif self.type_mouvement in ['SORTIE', 'ALIMENTATION_CAISSE']:
            self.solde_apres = self.solde_avant - self.montant
        
        # Sauvegarder le mouvement
        super().save(*args, **kwargs)
        
        # Appliquer les effets financiers uniquement lors de la création
        if is_new:
            caisse_generale = CaisseGenerale.get_instance()
            if self.type_mouvement == 'ENTREE':
                # Créditer la réserve
                caisse_generale.solde_reserve = (caisse_generale.solde_reserve or 0) + self.montant
                caisse_generale.save(update_fields=['solde_reserve', 'date_mise_a_jour'])
            elif self.type_mouvement == 'SORTIE':
                # Débiter la réserve
                caisse_generale.solde_reserve = (caisse_generale.solde_reserve or 0) - self.montant
                caisse_generale.save(update_fields=['solde_reserve', 'date_mise_a_jour'])
            elif self.type_mouvement == 'ALIMENTATION_CAISSE' and self.caisse_destination:
                # Débiter la réserve et créditer la caisse destinataire
                caisse_generale.solde_reserve = (caisse_generale.solde_reserve or 0) - self.montant
                caisse_generale.save(update_fields=['solde_reserve', 'date_mise_a_jour'])
                
                # Crédite la caisse et trace le mouvement côté caisse
                self.caisse_destination.fond_disponible = (self.caisse_destination.fond_disponible or 0) + self.montant
                self.caisse_destination.save(update_fields=['fond_disponible'])
                
                # Créer un mouvement de réception côté caisse
                MouvementFond.objects.create(
                    caisse=self.caisse_destination,
                    type_mouvement='RECEPTION_GENERALE',
                    montant=self.montant,
                    description='Alimentation reçue de la Caisse Générale',
                    utilisateur=self.utilisateur
                )
            
            # Synchroniser la somme des caisses après mise à jour
            try:
                caisse_generale.recalculer_total_caisses()
            except Exception:
                pass


class Depense(models.Model):
    """Modèle simplifié pour les dépenses d'une caisse.
    Champs demandés: datedepense, Objectifdepense, montantdepense, observation (optionnel).
    On conserve le lien à la `caisse` et l'utilisateur pour la traçabilité.
    """
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='depenses')
    datedepense = models.DateField(default=timezone.now, help_text="Date de la dépense")
    Objectifdepense = models.TextField(blank=True, default='', help_text="Objectif de la dépense")
    montantdepense = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Montant de la dépense en FCFA")
    observation = models.TextField(blank=True, help_text="Observation (optionnel)")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  help_text="Utilisateur qui a créé la dépense")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model metadata for Depense."""
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-datedepense', '-date_creation']
        indexes = [
            models.Index(fields=['caisse']),
            models.Index(fields=['datedepense']),
        ]

    def __str__(self):
        return f"{self.Objectifdepense[:30]} - {self.caisse.nom_association} ({self.montantdepense} FCFA)"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Bloquer si aucun exercice actif pour la caisse
        if self.caisse_id:
            assert_exercice_ouvert(self.caisse)
        if self.montantdepense is None or self.montantdepense <= 0:
            raise ValidationError("Le montant de la dépense doit être positif.")
        return True
    
    # Méthode d'annulation supprimée: les champs 'statut', 'notes_rejet', 'date_approbation' n'existent pas dans ce modèle simplifié.


class RapportActivite(models.Model):
    """Modèle pour les rapports d'activité générés par le système"""
    TYPE_RAPPORT_CHOICES = [
        ('MEMBRES', 'Liste des membres'),
        ('PRETS', 'Rapport des prêts'),
        ('COTISATIONS', 'Rapport des cotisations'),
        ('DEPENSES', 'Rapport des dépenses'),
        ('GENERAL', 'Rapport général'),
        ('CAISSE_GENERALE', 'Rapport caisse générale'),
    ]
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('GENERE', 'Généré'),
        ('ECHEC', 'Échec'),
    ]
    
    type_rapport = models.CharField(max_length=20, choices=TYPE_RAPPORT_CHOICES)
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='rapports_activite', null=True, blank=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    # Fichier généré
    fichier_pdf = models.FileField(upload_to='rapports/', null=True, blank=True)
    date_generation = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    genere_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rapports_generes')
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for RapportActivite."""
        verbose_name = "Rapport d'activité"
        verbose_name_plural = "Rapports d'activité"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['type_rapport']),
            models.Index(fields=['caisse']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_creation']),
        ]
    
    def __str__(self):
        caisse_nom = self.caisse.nom_association if self.caisse else "Général"
        return f"Rapport {self.get_type_rapport_display()} - {caisse_nom} ({self.get_statut_display()})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Vérifier que les dates sont cohérentes
        if self.date_debut and self.date_fin and self.date_debut > self.date_fin:
            raise ValidationError("La date de début doit être antérieure à la date de fin.")
        
        # Certains types de rapports nécessitent une caisse
        if self.type_rapport in ['MEMBRES', 'PRETS', 'COTISATIONS', 'DEPENSES'] and not self.caisse:
            raise ValidationError(f"Le rapport de type {self.get_type_rapport_display()} nécessite une caisse spécifique.")
    
    def save(self, *args, **kwargs):
        # Si le statut change vers GENERE, mettre à jour la date de génération
        if self.pk and self.statut == 'GENERE' and not self.date_generation:
            self.date_generation = timezone.now()
        
        super().save(*args, **kwargs)


class SalaireAgent(models.Model):
    """Modèle pour gérer les salaires mensuels des agents"""
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('PAYE', 'Payé'),
        ('ANNULE', 'Annulé'),
    ]
    
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='salaires')
    mois = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    annee = models.IntegerField()
    
    # Salaires et bonus
    salaire_base = models.DecimalField(max_digits=15, decimal_places=2, help_text="Salaire fixe mensuel")
    bonus_caisses = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Bonus basé sur les nouvelles caisses créées")
    prime_performance = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Prime de performance additionnelle")
    
    # Totaux
    total_brut = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_net = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Informations de paiement
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_paiement = models.DateTimeField(null=True, blank=True)
    mode_paiement = models.CharField(max_length=50, blank=True, help_text="Mode de paiement (virement, chèque, espèce, etc.)")
    
    # Métadonnées
    notes = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        """Django model metadata for SalaireAgent."""
        verbose_name = "Salaire Agent"
        verbose_name_plural = "Salaires Agents"
        ordering = ['-annee', '-mois', 'agent']
        unique_together = ['agent', 'mois', 'annee']
        indexes = [
            models.Index(fields=['agent']),
            models.Index(fields=['mois', 'annee']),
            models.Index(fields=['statut']),
        ]
    
    def __str__(self):
        return f"Salaire {self.agent.nom_complet} - {self.mois}/{self.annee}"
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement les totaux
        self.total_brut = self.salaire_base + self.bonus_caisses + self.prime_performance
        self.total_net = self.total_brut - self.deductions
        
        super().save(*args, **kwargs)
    
    @property
    def periode(self):
        """Retourne la période sous forme de texte"""
        from datetime import datetime
        try:
            date = datetime(self.annee, self.mois, 1)
            return date.strftime('%B %Y')
        except:
            return f"{self.mois}/{self.annee}"
    
    @property
    def nombre_nouvelles_caisses(self):
        """Retourne le nombre de nouvelles caisses créées par l'agent dans le mois"""
        from django.db.models import Q
        from datetime import datetime
        
        # Calculer le premier et dernier jour du mois
        debut_mois = datetime(self.annee, self.mois, 1)
        if self.mois == 12:
            fin_mois = datetime(self.annee + 1, 1, 1) - timezone.timedelta(days=1)
        else:
            fin_mois = datetime(self.annee, self.mois + 1, 1) - timezone.timedelta(days=1)
        
        return self.agent.caisses.filter(
            date_creation__gte=debut_mois,
            date_creation__lte=fin_mois
        ).count()
    
    def calculer_bonus_caisses(self, montant_par_caisse=5000):
        """Calcule le bonus basé sur le nombre de nouvelles caisses créées"""
        nombre_caisses = self.nombre_nouvelles_caisses
        self.bonus_caisses = nombre_caisses * montant_par_caisse
        self.save()
        return self.bonus_caisses


class FichePaie(models.Model):
    """Modèle pour générer et stocker les fiches de paie des agents"""
    TYPE_FICHE_CHOICES = [
        ('MOIS', 'Fiche mensuelle'),
        ('TRIMESTRE', 'Fiche trimestrielle'),
        ('ANNEE', 'Fiche annuelle'),
    ]
    
    salaire = models.OneToOneField(SalaireAgent, on_delete=models.CASCADE, related_name='fiche_paie')
    type_fiche = models.CharField(max_length=20, choices=TYPE_FICHE_CHOICES, default='MOIS')
    
    # Informations de l'agent
    nom_agent = models.CharField(max_length=300)
    matricule = models.CharField(max_length=50)
    poste = models.CharField(max_length=100, default="Agent de terrain")
    
    # Détails du salaire
    salaire_base = models.DecimalField(max_digits=15, decimal_places=2)
    bonus_caisses = models.DecimalField(max_digits=15, decimal_places=2)
    prime_performance = models.DecimalField(max_digits=15, decimal_places=2)
    total_brut = models.DecimalField(max_digits=15, decimal_places=2)
    deductions = models.DecimalField(max_digits=15, decimal_places=2)
    total_net = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Informations de la période
    mois = models.IntegerField()
    annee = models.IntegerField()
    nombre_nouvelles_caisses = models.IntegerField(default=0)
    
    # Fichier PDF généré
    fichier_pdf = models.FileField(upload_to='fiches_paie/', null=True, blank=True)
    date_generation = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    genere_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='fiches_paie_generes')
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        """Django model metadata for FichePaie."""
        verbose_name = "Fiche de paie"
        verbose_name_plural = "Fiches de paie"
        ordering = ['-annee', '-mois', 'nom_agent']
        indexes = [
            models.Index(fields=['salaire']),
            models.Index(fields=['mois', 'annee']),
            models.Index(fields=['date_generation']),
        ]
    
    def __str__(self):
        return f"Fiche de paie {self.nom_agent} - {self.mois}/{self.annee}"
    
    def save(self, *args, **kwargs):
        # Mettre à jour automatiquement les informations depuis le salaire
        if self.salaire:
            self.nom_agent = self.salaire.agent.nom_complet
            self.matricule = self.salaire.agent.matricule
            self.salaire_base = self.salaire.salaire_base
            self.bonus_caisses = self.salaire.bonus_caisses
            self.prime_performance = self.salaire.prime_performance
            self.total_brut = self.salaire.total_brut
            self.deductions = self.salaire.deductions
            self.total_net = self.salaire.total_net
            self.mois = self.salaire.mois
            self.annee = self.salaire.annee
            self.nombre_nouvelles_caisses = self.salaire.nombre_nouvelles_caisses
        
        super().save(*args, **kwargs)
    
    @property
    def periode(self):
        """Retourne la période sous forme de texte"""
        from datetime import datetime
        try:
            date = datetime(self.annee, self.mois, 1)
            return date.strftime('%B %Y')
        except:
            return f"{self.mois}/{self.annee}"
    
    def generer_pdf(self, user=None):
        """Génère le PDF de la fiche de paie"""
        from .utils import generate_fiche_paie_pdf
        
        if user:
            self.genere_par = user
        
        try:
            pdf_file = generate_fiche_paie_pdf(self)
            self.fichier_pdf = pdf_file
            self.date_generation = timezone.now()
            self.save()
            return True
        except Exception as e:
            print(f"Erreur lors de la génération du PDF: {e}")
            return False



