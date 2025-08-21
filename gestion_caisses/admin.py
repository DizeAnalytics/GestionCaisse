from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
import random
import string
from .models import (
    Region, Prefecture, Commune, Canton, Village, Agent,
    Caisse, Membre, Pret, Echeance, MouvementFond, 
    VirementBancaire, AuditLog, Notification, PresidentGeneral, Parametre,
    CaisseGenerale, CaisseGeneraleMouvement, RapportActivite
)
from .utils import create_credentials_pdf_response, create_agent_credentials_pdf_response
from .services import PretService
from .permissions import AgentAdminMixin, AgentPermissions


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'date_creation']
    search_fields = ['nom', 'code']
    ordering = ['nom']
    list_per_page = 20
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Prefecture)
class PrefectureAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'region', 'date_creation']
    list_filter = ['region']
    search_fields = ['nom', 'code']
    ordering = ['region', 'nom']
    list_per_page = 20
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'prefecture', 'region', 'date_creation']
    list_filter = ['prefecture__region', 'prefecture']
    search_fields = ['nom', 'code']
    ordering = ['prefecture__region', 'prefecture', 'nom']
    list_per_page = 20
    
    def region(self, obj):
        return obj.prefecture.region.nom
    region.short_description = 'Région'


@admin.register(Canton)
class CantonAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'commune', 'prefecture', 'region', 'date_creation']
    list_filter = ['commune__prefecture__region', 'commune__prefecture', 'commune']
    search_fields = ['nom', 'code']
    ordering = ['commune__prefecture__region', 'commune__prefecture', 'commune', 'nom']
    list_per_page = 20
    
    def prefecture(self, obj):
        return obj.commune.prefecture.nom
    prefecture.short_description = 'Préfecture'
    
    def region(self, obj):
        return obj.commune.prefecture.region.nom
    region.short_description = 'Région'


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'canton', 'commune', 'prefecture', 'region', 'date_creation']
    list_filter = ['canton__commune__prefecture__region', 'canton__commune__prefecture', 'canton__commune', 'canton']
    search_fields = ['nom', 'code']
    ordering = ['canton__commune__prefecture__region', 'canton__commune__prefecture', 'canton__commune', 'canton', 'nom']
    list_per_page = 20
    
    def commune(self, obj):
        return obj.canton.commune.nom
    commune.short_description = 'Commune'
    
    def prefecture(self, obj):
        return obj.canton.commune.prefecture.nom
    prefecture.short_description = 'Préfecture'
    
    def region(self, obj):
        return obj.canton.commune.prefecture.region.nom
    region.short_description = 'Région'


class AgentCreationForm(forms.ModelForm):
    """Formulaire personnalisé pour la création d'agents avec génération automatique du compte utilisateur"""
    
    # Informations pour le compte utilisateur
    creer_compte_utilisateur = forms.BooleanField(
        initial=True, 
        required=False,
        label="Créer un compte utilisateur pour cet agent",
        help_text="Cochez cette case pour créer automatiquement un compte utilisateur"
    )
    
    class Meta:
        model = Agent
        fields = [
            'nom', 'prenoms', 'numero_carte_electeur', 'date_naissance', 'adresse', 'numero_telephone', 'email',
            'date_embauche', 'statut', 'region', 'prefecture', 'notes'
        ]
    
    def clean_numero_carte_electeur(self):
        numero_carte = self.cleaned_data['numero_carte_electeur']
        if Agent.objects.filter(numero_carte_electeur=numero_carte).exists():
            raise ValidationError("Ce numéro de carte d'électeur existe déjà.")
        return numero_carte
    
    def generate_username(self, nom, prenoms):
        """Génère un nom d'utilisateur unique basé sur le nom et prénoms"""
        base_username = f"agent_{nom.lower()}{prenoms.split()[0].lower()}"
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username
    
    def generate_password(self):
        """Génère un mot de passe sécurisé"""
        # Générer un mot de passe de 8 caractères avec lettres et chiffres
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(8))


class CaisseCreationForm(forms.ModelForm):
    """Formulaire personnalisé pour la création de caisses avec génération automatique des comptes utilisateurs"""
    
    # Informations de la Présidente
    presidente_nom = forms.CharField(max_length=100, label="Nom de la Présidente")
    presidente_prenoms = forms.CharField(max_length=200, label="Prénoms de la Présidente")
    presidente_numero_carte = forms.CharField(max_length=20, label="Numéro de carte d'électeur (Présidente)")
    presidente_date_naissance = forms.DateField(label="Date de naissance (Présidente)")
    presidente_adresse = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label="Adresse (Présidente)")
    presidente_telephone = forms.CharField(max_length=20, label="Numéro de téléphone (Présidente)")
    
    # Informations de la Secrétaire
    secretaire_nom = forms.CharField(max_length=100, label="Nom de la Secrétaire")
    secretaire_prenoms = forms.CharField(max_length=200, label="Prénoms de la Secrétaire")
    secretaire_numero_carte = forms.CharField(max_length=20, label="Numéro de carte d'électeur (Secrétaire)")
    secretaire_date_naissance = forms.DateField(label="Date de naissance (Secrétaire)")
    secretaire_adresse = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label="Adresse (Secrétaire)")
    secretaire_telephone = forms.CharField(max_length=20, label="Numéro de téléphone (Secrétaire)")
    
    # Informations de la Trésorière
    tresoriere_nom = forms.CharField(max_length=100, label="Nom de la Trésorière")
    tresoriere_prenoms = forms.CharField(max_length=200, label="Prénoms de la Trésorière")
    tresoriere_numero_carte = forms.CharField(max_length=20, label="Numéro de carte d'électeur (Trésorière)")
    tresoriere_date_naissance = forms.DateField(label="Date de naissance (Trésorière)")
    tresoriere_adresse = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label="Adresse (Trésorière)")
    tresoriere_telephone = forms.CharField(max_length=20, label="Numéro de téléphone (Trésorière)")
    
    class Meta:
        model = Caisse
        fields = [
            'agent', 'nom_association', 'description', 'region', 'prefecture', 'commune', 
            'canton', 'village', 'statut', 'fond_initial', 'notes'
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Vérifier qu'un agent est sélectionné
        if not cleaned_data.get('agent'):
            raise ValidationError("Un agent responsable doit être sélectionné pour cette caisse.")
        
        # Vérifier que les numéros de carte d'électeur sont uniques
        numero_cartes = [
            cleaned_data.get('presidente_numero_carte'),
            cleaned_data.get('secretaire_numero_carte'),
            cleaned_data.get('tresoriere_numero_carte')
        ]
        
        if len(set(numero_cartes)) != 3:
            raise ValidationError("Les numéros de carte d'électeur doivent être différents pour chaque responsable.")
        
        # Vérifier que les numéros de carte n'existent pas déjà
        for numero in numero_cartes:
            if Membre.objects.filter(numero_carte_electeur=numero).exists():
                raise ValidationError(f"Le numéro de carte d'électeur {numero} existe déjà.")
        
        return cleaned_data
    
    def generate_username(self, nom, prenoms):
        """Génère un nom d'utilisateur unique basé sur le nom et prénoms"""
        base_username = f"{nom.lower()}{prenoms.split()[0].lower()}"
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username
    
    def generate_password(self):
        """Génère un mot de passe sécurisé"""
        # Générer un mot de passe de 8 caractères avec lettres et chiffres
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(8))


class CaisseEditForm(forms.ModelForm):
    """Formulaire pour la modification des caisses existantes (sans les champs des responsables)"""
    
    class Meta:
        model = Caisse
        fields = [
            'agent', 'nom_association', 'description', 'region', 'prefecture', 'commune', 
            'canton', 'village', 'statut', 'fond_initial', 'notes'
        ]


class CaisseInline(admin.TabularInline):
    model = Caisse
    extra = 0
    readonly_fields = ['code', 'nom_association', 'statut', 'date_creation']
    fields = ['code', 'nom_association', 'statut', 'date_creation']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class MembreInline(admin.TabularInline):
    model = Membre
    extra = 0
    readonly_fields = ['date_adhesion', 'date_derniere_activite']
    fields = [
        'numero_carte_electeur', 'nom', 'prenoms', 'date_naissance', 
        'adresse', 'numero_telephone', 'role', 'statut'
    ]


class PretInline(admin.TabularInline):
    model = Pret
    extra = 0
    readonly_fields = ['numero_pret', 'date_demande']
    fields = ['numero_pret', 'membre', 'montant_demande', 'statut', 'date_demande']


class EcheanceInline(admin.TabularInline):
    """Inline pour afficher les échéances d'un prêt"""
    model = Echeance
    extra = 0
    readonly_fields = ['numero_echeance', 'montant_echeance', 'date_echeance']
    fields = ['numero_echeance', 'montant_echeance', 'date_echeance', 'montant_paye', 'statut', 'date_paiement']
    
    def get_queryset(self, request):
        """Optimiser les requêtes"""
        return super().get_queryset(request).select_related('pret')


# Dashboard des prêts
class PretDashboardAdmin(admin.ModelAdmin):
    """Dashboard des prêts avec statistiques détaillées"""
    change_list_template = 'admin/gestion_caisses/pret_dashboard/change_list.html'
    change_form_template = 'admin/gestion_caisses/pret/change_form.html'
    
    # Configuration de la liste des prêts avec plus de détails
    list_display = [
        'numero_pret', 'membre_complet', 'caisse', 'montant_demande', 
        'montant_accord', 'montant_restant_affiche', 'taux_interet', 
        'duree_mois', 'statut_colore', 'date_demande', 'progression_remboursement', 'resume_echeances'
    ]
    
    list_filter = [
        'statut', 'caisse__region', 'caisse__prefecture', 'caisse__commune',
        'date_demande', 'date_validation', 'date_decaissement'
    ]
    
    search_fields = [
        'numero_pret', 'membre__nom', 'membre__prenoms', 'membre__numero_carte_electeur',
        'caisse__nom_association', 'caisse__code'
    ]
    
    ordering = ['-date_demande']
    list_per_page = 50
    
    readonly_fields = [
        'numero_pret', 'date_demande', 'montant_restant', 'nombre_echeances_payees'
    ]
    
    fieldsets = (
        ('Informations du prêt', {
            'fields': ('numero_pret', 'membre', 'caisse', 'motif')
        }),
        ('Détails financiers', {
            'fields': ('montant_demande', 'montant_accord', 'taux_interet', 'duree_mois')
        }),
        ('Suivi du prêt', {
            'fields': ('statut', 'date_validation', 'date_decaissement', 'date_remboursement_complet')
        }),
        ('Remboursements', {
            'fields': ('montant_rembourse', 'nombre_echeances', 'nombre_echeances_payees')
        }),
        ('Notes et rejet', {
            'fields': ('motif_rejet', 'notes'),
            'classes': ('collapse',)
        }),
    )
    
    # Inlines pour afficher les échéances
    inlines = [EcheanceInline]
    
    def get_queryset(self, request):
        """Optimiser les requêtes en préchargeant les relations"""
        return super().get_queryset(request).select_related(
            'membre', 'caisse', 'caisse__region', 'caisse__prefecture', 'caisse__commune'
        ).prefetch_related('echeances')

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """Ajoute un résumé visuel du prêt au-dessus du formulaire d'édition."""
        if obj is not None:
            try:
                obj.get_or_create_echeances()
            except Exception:
                pass

            total_echeances = obj.echeances.count()
            echeances_payees = obj.echeances.filter(statut='PAYE').count()
            echeances_en_retard = obj.echeances.filter(statut='EN_RETARD').count()
            echeances_a_payer = obj.echeances.filter(statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']).count()
            prochaine = obj.get_prochaine_echeance()

            progression = 0
            if obj.montant_accord:
                try:
                    progression = float((obj.montant_rembourse / obj.montant_accord) * 100)
                except Exception:
                    progression = 0

            context['pret_summary'] = {
                'numero_pret': obj.numero_pret,
                'statut': obj.statut,
                'montant_accord': obj.montant_accord,
                'montant_interet': getattr(obj, 'montant_interet_calcule', 0),
                'net_a_payer': getattr(obj, 'total_a_rembourser', 0),
                'montant_rembourse': obj.montant_rembourse,
                'montant_restant': getattr(obj, 'montant_restant', 0),
                'echeances': {
                    'total': total_echeances,
                    'payees': echeances_payees,
                    'a_payer': echeances_a_payer,
                    'en_retard': echeances_en_retard,
                },
                'prochaine_echeance': {
                    'date': getattr(prochaine, 'date_echeance', None),
                    'montant': getattr(prochaine, 'montant_echeance', None),
                    'numero': getattr(prochaine, 'numero_echeance', None),
                } if prochaine else None,
                'progression': progression,
            }

        return super().render_change_form(request, context, add, change, form_url, obj)
    
    # Méthodes pour afficher des informations calculées
    def membre_complet(self, obj):
        """Affiche le nom complet du membre avec son numéro de carte"""
        return f"{obj.membre.nom_complet} ({obj.membre.numero_carte_electeur})"
    membre_complet.short_description = 'Membre'
    membre_complet.admin_order_field = 'membre__nom'
    
    def montant_restant_affiche(self, obj):
        """Affiche le montant restant avec formatage"""
        if obj.montant_accord:
            montant_restant = obj.montant_accord - obj.montant_rembourse
            if montant_restant > 0:
                return f"{montant_restant:,.0f} FCFA"
            else:
                return "0 FCFA"
        return "N/A"
    montant_restant_affiche.short_description = 'Montant Restant'
    
    def statut_colore(self, obj):
        """Affiche le statut avec des couleurs et icônes"""
        statut_colors = {
            'EN_ATTENTE': ('⏳ En Attente', '#FF9800'),
            'EN_ATTENTE_ADMIN': ('⏳ En Attente Admin', '#FF5722'),
            'VALIDE': ('✅ Validé', '#4CAF50'),
            'REJETE': ('❌ Rejeté', '#F44336'),
            'BLOQUE': ('🚫 Bloqué', '#9C27B0'),
            'EN_COURS': ('🚀 En Cours', '#2196F3'),
            'REMBOURSE': ('💰 Remboursé', '#4CAF50'),
            'EN_RETARD': ('⚠️ En Retard', '#FF5722'),
        }
        
        statut_text, color = statut_colors.get(obj.statut, (obj.statut, '#757575'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, statut_text
        )
    statut_colore.short_description = 'Statut'
    statut_colore.admin_order_field = 'statut'
    
    def progression_remboursement(self, obj):
        """Affiche une barre de progression pour le remboursement"""
        if obj.montant_accord and obj.montant_accord > 0:
            pourcentage = (obj.montant_rembourse / obj.montant_accord) * 100
            couleur = '#4CAF50' if pourcentage >= 100 else '#FF9800' if pourcentage >= 50 else '#F44336'
            
            return format_html(
                '<div style="width: 100px; background-color: #f0f0f0; border-radius: 10px; overflow: hidden;">'
                '<div style="width: {}%; height: 20px; background-color: {}; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: bold;">'
                '{}%</div></div>',
                min(pourcentage, 100), couleur, round(pourcentage, 1)
            )
        return "N/A"
    progression_remboursement.short_description = 'Progression'
    
    def taux_interet(self, obj):
        """Affiche le taux d'intérêt avec le symbole %"""
        return f"{obj.taux_interet}%"
    taux_interet.short_description = 'Taux'
    taux_interet.admin_order_field = 'taux_interet'
    
    def resume_echeances(self, obj):
        """Affiche un résumé des échéances du prêt"""
        # Backfill si nécessaire
        obj.get_or_create_echeances()
        total_echeances = obj.echeances.count()
        echeances_payees = obj.echeances.filter(statut='PAYE').count()
        echeances_en_retard = obj.echeances.filter(statut='EN_RETARD').count()
        
        if total_echeances == 0:
            return "Aucune échéance"
        
        resume = f"{echeances_payees}/{total_echeances} payées"
        if echeances_en_retard > 0:
            resume += f" ({echeances_en_retard} en retard)"
        
        return resume
    resume_echeances.short_description = 'Échéances'
    
    # Actions personnalisées
    actions = ['valider_prets', 'rejeter_prets', 'mettre_en_attente_prets']
    
    def valider_prets(self, request, queryset):
        """Action pour valider plusieurs prêts"""
        from .services import PretService
        count = 0
        for pret in queryset.filter(statut='EN_ATTENTE_ADMIN'):
            try:
                PretService.valider_pret(pret, request.user)
                count += 1
            except Exception as e:
                self.message_user(request, f"Erreur lors de la validation du prêt {pret.numero_pret}: {str(e)}", level=messages.ERROR)
        
        self.message_user(request, f"{count} prêt(s) validé(s) avec succès.")
    valider_prets.short_description = "Valider les prêts sélectionnés"
    
    def rejeter_prets(self, request, queryset):
        """Action pour rejeter plusieurs prêts"""
        from .services import PretService
        count = 0
        for pret in queryset.filter(statut__in=['EN_ATTENTE', 'EN_ATTENTE_ADMIN']):
            try:
                PretService.rejeter_pret(pret, request.user, "Rejet en lot par l'administrateur")
                count += 1
            except Exception as e:
                self.message_user(request, f"Erreur lors du rejet du prêt {pret.numero_pret}: {str(e)}", level=messages.ERROR)
        
        self.message_user(request, f"{count} prêt(s) rejeté(s) avec succès.")
    rejeter_prets.short_description = "Rejeter les prêts sélectionnés"
    
    def mettre_en_attente_prets(self, request, queryset):
        """Action pour mettre en attente plusieurs prêts"""
        from .services import PretService
        count = 0
        for pret in queryset.filter(statut__in=['EN_ATTENTE', 'EN_ATTENTE_ADMIN']):
            try:
                PretService.mettre_en_attente_pret(pret, request.user, "Mis en attente en lot par l'administrateur")
                count += 1
            except Exception as e:
                self.message_user(request, f"Erreur lors de la mise en attente du prêt {pret.numero_pret}: {str(e)}", level=messages.ERROR)
        
        self.message_user(request, f"{count} prêt(s) mis en attente avec succès.")
    mettre_en_attente_prets.short_description = "Mettre en attente les prêts sélectionnés"
    
    def changelist_view(self, request, extra_context=None):
        """Vue personnalisée pour afficher les statistiques des prêts"""
        extra_context = extra_context or {}
        
        from django.db.models import Sum, Count, Q, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        # Périodes de comparaison
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        three_months_ago = today - timedelta(days=90)
        
        # Statistiques globales des prêts
        total_prets = Pret.objects.count()
        total_montant_prets = Pret.objects.aggregate(total=Sum('montant_accord'))['total'] or 0
        total_montant_rembourse = Pret.objects.aggregate(total=Sum('montant_rembourse'))['total'] or 0
        # Calculer le montant restant en Python car c'est une propriété calculée
        total_montant_restant = total_montant_prets - total_montant_rembourse
        
        # Prêts par statut
        prets_par_statut = Pret.objects.values('statut').annotate(
            count=Count('id'),
            montant_total=Sum('montant_accord'),
            montant_rembourse=Sum('montant_rembourse')
        ).order_by('-count')
        
        # Prêts en retard (échéances dépassées)
        prets_en_retard = Pret.objects.filter(
            echeances__date_echeance__lt=today,
            echeances__statut='EN_ATTENTE',
            statut__in=['VALIDE', 'EN_COURS']
        ).distinct()
        
        # Calculer le montant en retard en Python
        montant_retard = sum(pret.montant_restant for pret in prets_en_retard)
        
        # Échéances en retard
        echeances_en_retard = Echeance.objects.filter(
            date_echeance__lt=today,
            statut='EN_ATTENTE'
        ).count()
        
        # Statistiques par région
        prets_par_region_raw = Pret.objects.values('caisse__region__nom').annotate(
            nombre_prets=Count('id'),
            montant_total=Sum('montant_accord'),
            montant_rembourse=Sum('montant_rembourse')
        ).order_by('-montant_total')
        
        # Calculer le montant restant en Python
        prets_par_region = []
        for region_data in prets_par_region_raw:
            montant_total = region_data['montant_total'] or 0
            montant_rembourse = region_data['montant_rembourse'] or 0
            region_data['montant_restant'] = montant_total - montant_rembourse
            prets_par_region.append(region_data)
        
        # Statistiques par caisse
        prets_par_caisse_raw = Pret.objects.values('caisse__nom_association').annotate(
            nombre_prets=Count('id'),
            montant_total=Sum('montant_accord'),
            montant_rembourse=Sum('montant_rembourse')
        ).order_by('-montant_total')[:10]
        
        # Calculer le montant restant en Python
        prets_par_caisse = []
        for caisse_data in prets_par_caisse_raw:
            montant_total = caisse_data['montant_total'] or 0
            montant_rembourse = caisse_data['montant_rembourse'] or 0
            caisse_data['montant_restant'] = montant_total - montant_rembourse
            prets_par_caisse.append(caisse_data)
        
        # Évolution des prêts (30 derniers jours)
        prets_30_jours = Pret.objects.filter(
            date_demande__gte=month_ago
        ).count()
        
        prets_90_jours = Pret.objects.filter(
            date_demande__gte=three_months_ago
        ).count()
        
        # Taux de remboursement par période
        taux_remboursement_30j = 0
        taux_remboursement_90j = 0
        
        if total_montant_prets > 0:
            taux_remboursement_30j = (total_montant_rembourse / total_montant_prets * 100)
            taux_remboursement_90j = (total_montant_rembourse / total_montant_prets * 100)
        
        # Prêts à risque (plus de 30 jours de retard)
        prets_risque = prets_en_retard.filter(
            echeances__date_echeance__lt=today - timedelta(days=30)
        ).distinct().count()
        
        extra_context.update({
            # Statistiques globales
            'total_prets': total_prets,
            'total_montant_prets': total_montant_prets,
            'total_montant_rembourse': total_montant_rembourse,
            'total_montant_restant': total_montant_restant,
            'taux_remboursement_global': (total_montant_rembourse / total_montant_prets * 100) if total_montant_prets > 0 else 0,
            
            # Prêts par statut
            'prets_par_statut': prets_par_statut,
            
            # Prêts en retard
            'prets_en_retard_count': prets_en_retard.count(),
            'montant_retard': montant_retard,
            'echeances_en_retard': echeances_en_retard,
            'prets_risque': prets_risque,
            
            # Statistiques géographiques
            'prets_par_region': prets_par_region,
            'prets_par_caisse': prets_par_caisse,
            
            # Évolution
            'prets_30_jours': prets_30_jours,
            'prets_90_jours': prets_90_jours,
            'taux_remboursement_30j': taux_remboursement_30j,
            'taux_remboursement_90j': taux_remboursement_90j,
            
            # Périodes
            'month_ago': month_ago,
            'three_months_ago': three_months_ago,
        })
        
        return super().changelist_view(request, extra_context)

# Enregistrer le nouveau dashboard des prêts
admin.site.register(Pret, PretDashboardAdmin)


@admin.register(Echeance)
class EcheanceAdmin(AgentAdminMixin, admin.ModelAdmin):
    list_display = ['pret', 'numero_echeance', 'montant_echeance', 'date_echeance', 'montant_paye', 'statut']
    list_filter = ['statut', 'pret__caisse', 'date_echeance']
    search_fields = ['pret__numero_pret', 'pret__membre__nom']
    ordering = ['pret', 'numero_echeance']
    list_per_page = 20


@admin.register(MouvementFond)
class MouvementFondAdmin(AgentAdminMixin, admin.ModelAdmin):
    list_display = [
        'caisse', 'type_mouvement', 'montant', 'solde_avant', 'solde_apres', 
        'date_mouvement', 'utilisateur'
    ]
    list_filter = ['type_mouvement', 'caisse__region', 'caisse__prefecture', 'caisse__commune', 'date_mouvement']
    search_fields = ['caisse__nom_association', 'description']
    ordering = ['-date_mouvement']
    list_per_page = 20
    readonly_fields = ['date_mouvement', 'solde_avant', 'solde_apres']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('caisse', 'type_mouvement', 'montant', 'description')
        }),
        ('Référence', {
            'fields': ('pret',)
        }),
        ('Soldes', {
            'fields': ('solde_avant', 'solde_apres'),
            'classes': ('collapse',)
        }),
        ('Traçabilité', {
            'fields': ('date_mouvement', 'utilisateur'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Calcule solde_avant/solde_apres et met à jour la caisse lors de la création depuis l'admin."""
        # Déterminer le solde avant
        caisse = obj.caisse
        solde_avant = caisse.fond_disponible

        # Calculer le solde après en fonction du type de mouvement
        if obj.type_mouvement == 'ALIMENTATION':
            solde_apres = solde_avant + obj.montant
        elif obj.type_mouvement == 'DECAISSEMENT':
            solde_apres = solde_avant - obj.montant
        elif obj.type_mouvement == 'REMBOURSEMENT':
            solde_apres = solde_avant + obj.montant
            caisse.montant_total_remboursements += obj.montant
        else:
            # Autres frais/autres: par défaut on soustrait
            solde_apres = solde_avant - obj.montant

        # Assigner les champs calculés
        obj.solde_avant = solde_avant
        obj.solde_apres = solde_apres
        if not obj.utilisateur:
            obj.utilisateur = request.user

        # Mettre à jour la caisse
        caisse.fond_disponible = solde_apres
        caisse.save()

        # Synchroniser la Caisse Générale (total des caisses)
        try:
            from .models import CaisseGenerale
            CaisseGenerale.get_instance().recalculer_total_caisses()
        except Exception:
            pass

        super().save_model(request, obj, form, change)


@admin.register(VirementBancaire)
class VirementBancaireAdmin(admin.ModelAdmin):
    list_display = [
        'caisse', 'numero_compte_cible', 'montant', 'statut', 
        'date_demande', 'date_execution', 'reference_bancaire'
    ]
    list_filter = ['statut', 'caisse__region', 'caisse__prefecture', 'caisse__commune', 'date_demande']
    search_fields = ['caisse__nom_association', 'reference_bancaire', 'numero_compte_cible']
    ordering = ['-date_demande']
    list_per_page = 20
    readonly_fields = ['date_demande']
    
    fieldsets = (
        ('Informations du virement', {
            'fields': ('caisse', 'numero_compte_cible', 'montant', 'description')
        }),
        ('Statut et dates', {
            'fields': ('statut', 'date_demande', 'date_execution')
        }),
        ('Référence bancaire', {
            'fields': ('reference_bancaire',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(CaisseGenerale)
class CaisseGeneraleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'solde_reserve', 'solde_total_caisses', 'solde_systeme', 'total_caisses_actuel', 'date_mise_a_jour']
    readonly_fields = ['solde_total_caisses', 'date_mise_a_jour', 'total_caisses_actuel']
    actions = ['recalculer_totaux']

    @admin.action(description="Recalculer la somme des caisses")
    def recalculer_totaux(self, request, queryset):
        for obj in queryset:
            obj.recalculer_total_caisses()
        self.message_user(request, "Sommes des caisses recalculées")

    @admin.display(description="Somme actuelle des caisses")
    def total_caisses_actuel(self, obj):
        from django.db.models import Sum
        from .models import Caisse
        total = Caisse.objects.aggregate(total=Sum('fond_disponible'))['total'] or 0
        return total


@admin.register(CaisseGeneraleMouvement)
class CaisseGeneraleMouvementAdmin(admin.ModelAdmin):
    list_display = ['type_mouvement', 'montant', 'caisse_destination', 'solde_avant', 'solde_apres', 'date_mouvement']
    list_filter = ['type_mouvement', 'date_mouvement']
    search_fields = ['description']
    readonly_fields = ['solde_avant', 'solde_apres', 'date_mouvement']

    fieldsets = (
        (None, {
            'fields': ('type_mouvement', 'montant', 'caisse_destination', 'description')
        }),
        ('Suivi', {
            'fields': ('solde_avant', 'solde_apres', 'utilisateur', 'date_mouvement'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        from .models import CaisseGenerale, MouvementFond
        cg = CaisseGenerale.get_instance()
        obj.utilisateur = obj.utilisateur or request.user
        obj.solde_avant = cg.solde_reserve

        if obj.type_mouvement == 'ENTREE':
            cg.solde_reserve = cg.solde_reserve + obj.montant
            obj.solde_apres = cg.solde_reserve
            cg.save(update_fields=['solde_reserve', 'date_mise_a_jour'])

        elif obj.type_mouvement == 'SORTIE':
            cg.solde_reserve = cg.solde_reserve - obj.montant
            obj.solde_apres = cg.solde_reserve
            cg.save(update_fields=['solde_reserve', 'date_mise_a_jour'])

        elif obj.type_mouvement == 'ALIMENTATION_CAISSE':
            if not obj.caisse_destination:
                from django.core.exceptions import ValidationError
                raise ValidationError("Sélectionnez une caisse destination")
            # Débiter la réserve
            cg.solde_reserve = cg.solde_reserve - obj.montant
            obj.solde_apres = cg.solde_reserve
            cg.save(update_fields=['solde_reserve', 'date_mise_a_jour'])
            # Créditer la caisse destination via un mouvement d'alimentation
            caisse = obj.caisse_destination
            solde_avant_caisse = caisse.fond_disponible
            caisse.fond_disponible = solde_avant_caisse + obj.montant
            caisse.save(update_fields=['fond_disponible'])
            MouvementFond.objects.create(
                caisse=caisse,
                type_mouvement='ALIMENTATION',
                montant=obj.montant,
                solde_avant=solde_avant_caisse,
                solde_apres=caisse.fond_disponible,
                description=f'Alimentation par la Caisse Générale',
                utilisateur=request.user
            )

        super().save_model(request, obj, form, change)


@admin.register(RapportActivite)
class RapportActiviteAdmin(admin.ModelAdmin):
    list_display = ['type_rapport', 'caisse', 'periode', 'statut', 'date_generation', 'genere_par']
    list_filter = ['type_rapport', 'statut', 'date_generation', 'caisse__region']
    search_fields = ['caisse__nom_association', 'notes']
    readonly_fields = ['date_generation', 'genere_par', 'donnees', 'fichier_pdf']
    actions = ['generer_rapports']

    fieldsets = (
        ('Paramètres', {
            'fields': ('type_rapport', 'caisse', 'date_debut', 'date_fin', 'notes')
        }),
        ('Résultat', {
            'fields': ('statut', 'date_generation', 'genere_par', 'donnees', 'fichier_pdf'),
            'classes': ('collapse',)
        })
    )

    @admin.display(description='Période')
    def periode(self, obj):
        if obj.date_debut and obj.date_fin:
            return f"{obj.date_debut.strftime('%d/%m/%Y')} → {obj.date_fin.strftime('%d/%m/%Y')}"
        return '-'

    @admin.action(description='Générer les rapports sélectionnés')
    def generer_rapports(self, request, queryset):
        from django.utils import timezone
        from .views import (
            generer_rapport_general_caisse, generer_rapport_financier_caisse,
            generer_rapport_prets_caisse, generer_rapport_membres_caisse,
            generer_rapport_echeances_caisse, generer_rapport_general_global,
            generer_rapport_financier_global, generer_rapport_prets_global,
            generer_rapport_membres_global, generer_rapport_echeances_global
        )
        from .utils import get_parametres_application, generate_rapport_pdf
        from django.core.files.base import ContentFile
        import json
        count_ok, count_err = 0, 0
        for rapport in queryset:
            try:
                caisse = rapport.caisse
                t = rapport.type_rapport
                if t == 'general':
                    if caisse:
                        data = generer_rapport_general_caisse(caisse, rapport.date_debut, rapport.date_fin)
                    else:
                        data = generer_rapport_general_global(rapport.date_debut, rapport.date_fin)
                elif t == 'financier':
                    data = generer_rapport_financier_caisse(caisse, rapport.date_debut, rapport.date_fin) if caisse else generer_rapport_financier_global(rapport.date_debut, rapport.date_fin)
                elif t == 'prets':
                    data = generer_rapport_prets_caisse(caisse, rapport.date_debut, rapport.date_fin) if caisse else generer_rapport_prets_global(rapport.date_debut, rapport.date_fin)
                elif t == 'membres':
                    data = generer_rapport_membres_caisse(caisse, rapport.date_debut, rapport.date_fin) if caisse else generer_rapport_membres_global(rapport.date_debut, rapport.date_fin)
                elif t == 'echeances':
                    data = generer_rapport_echeances_caisse(caisse, rapport.date_debut, rapport.date_fin) if caisse else generer_rapport_echeances_global(rapport.date_debut, rapport.date_fin)
                else:
                    raise ValueError('Type de rapport invalide')

                # Enregistrer les données JSON
                rapport.donnees = data
                rapport.statut = 'GENERE'
                rapport.date_generation = timezone.now()
                rapport.genere_par = request.user

                # Générer un PDF formaté
                try:
                    pdf_bytes = generate_rapport_pdf(rapport)
                    rapport.fichier_pdf.save(f"rapport_{t}_{rapport.pk or 'new'}.pdf", ContentFile(pdf_bytes), save=False)
                except Exception as e:
                    # fallback texte si erreur pdf
                    fallback = bytes(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
                    rapport.fichier_pdf.save(f"rapport_{t}_{rapport.pk or 'new'}.txt", ContentFile(fallback), save=False)

                rapport.save()
                count_ok += 1
            except Exception as e:
                rapport.statut = 'ECHEC'
                rapport.notes = (rapport.notes or '') + f"\nErreur: {e}"
                rapport.save(update_fields=['statut', 'notes'])
                count_err += 1
        self.message_user(request, f"{count_ok} rapport(s) généré(s), {count_err} en échec")

# Dashboard d'audit personnalisé
class AuditDashboardAdmin(admin.ModelAdmin):
    """Dashboard d'audit pour visualiser l'activité des utilisateurs"""
    change_list_template = 'admin/gestion_caisses/auditlog/change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        """Vue personnalisée pour afficher des statistiques d'audit"""
        extra_context = extra_context or {}
        
        # Statistiques d'audit
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Actions aujourd'hui
        today = timezone.now().date()
        actions_today = AuditLog.objects.filter(date_action__date=today).count()
        
        # Actions cette semaine
        week_ago = today - timedelta(days=7)
        actions_week = AuditLog.objects.filter(date_action__date__gte=week_ago).count()
        
        # Actions ce mois
        month_ago = today - timedelta(days=30)
        actions_month = AuditLog.objects.filter(date_action__date__gte=month_ago).count()
        
        # Actions par type
        actions_by_type = AuditLog.objects.values('action').annotate(count=Count('id')).order_by('-count')
        
        # Actions par utilisateur
        actions_by_user = AuditLog.objects.values('utilisateur__username').annotate(count=Count('id')).order_by('-count')[:10]
        
        # Actions par modèle
        actions_by_model = AuditLog.objects.values('modele').annotate(count=Count('id')).order_by('-count')
        
        # Actions par heure (pour les graphiques)
        from django.db.models.functions import ExtractHour
        
        try:
            actions_by_hour = AuditLog.objects.filter(
                date_action__date=today
            ).annotate(
                hour=ExtractHour('date_action')
            ).values('hour').annotate(count=Count('id')).order_by('hour')
        except:
            # Fallback pour SQLite si ExtractHour ne fonctionne pas
            actions_by_hour = []
        
        # Actions suspectes (même IP, beaucoup d'échecs)
        suspicious_ips = AuditLog.objects.values('ip_adresse').annotate(
            count=Count('id')
        ).filter(count__gt=100).order_by('-count')[:5]
        
        extra_context.update({
            'actions_today': actions_today,
            'actions_week': actions_week,
            'actions_month': actions_month,
            'actions_by_type': actions_by_type,
            'actions_by_user': actions_by_user,
            'actions_by_model': actions_by_model,
            'actions_by_hour': actions_by_hour,
            'suspicious_ips': suspicious_ips,
        })
        
        return super().changelist_view(request, extra_context)

# Enregistrer le nouveau dashboard d'audit
admin.site.register(AuditLog, AuditDashboardAdmin)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'destinataire', 'type_notification', 'titre', 'statut', 'date_creation'
    ]
    list_filter = ['type_notification', 'statut', 'date_creation']
    search_fields = ['destinataire__username', 'titre', 'message']
    ordering = ['-date_creation']
    list_per_page = 50
    readonly_fields = ['date_creation']
    
    fieldsets = (
        ('Destinataire', {
            'fields': ('destinataire', 'type_notification')
        }),
        ('Contenu', {
            'fields': ('titre', 'message')
        }),
        ('Contexte', {
            'fields': ('caisse', 'pret', 'lien_action')
        }),
        ('Statut', {
            'fields': ('statut', 'date_lecture', 'date_traitement')
        }),
        ('Dates', {
            'fields': ('date_creation',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = [
        'matricule', 'nom_complet', 'numero_carte_electeur', 'statut', 'region', 'prefecture', 
        'nombre_caisses', 'caisses_actives', 'date_embauche'
    ]
    list_filter = ['statut', 'region', 'prefecture', 'date_embauche', 'date_creation']
    search_fields = ['matricule', 'numero_carte_electeur', 'nom', 'prenoms', 'email']
    ordering = ['nom', 'prenoms']
    list_per_page = 20
    def get_readonly_fields(self, request, obj=None):
        """Retourne les champs en lecture seule selon le contexte"""
        readonly = ['date_creation', 'date_derniere_activite']
        
        if obj is not None:  # Modification d'un agent existant
            readonly.extend(['nombre_caisses', 'caisses_actives'])
        
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Retourne les fieldsets appropriés selon le contexte"""
        if obj is None:  # Création d'un nouvel agent
            return (
                ('Informations personnelles', {
                    'fields': ('nom', 'prenoms', 'numero_carte_electeur', 'date_naissance', 'adresse', 'numero_telephone', 'email')
                }),
                ('Informations professionnelles', {
                    'fields': ('date_embauche', 'statut')
                }),
                ('Zone de responsabilité', {
                    'fields': ('region', 'prefecture')
                }),
                ('Compte utilisateur', {
                    'fields': ('creer_compte_utilisateur',),
                    'classes': ('collapse',),
                    'description': 'Cochez cette case pour créer automatiquement un compte utilisateur pour cet agent.'
                }),
                ('Notes', {
                    'fields': ('notes',),
                    'classes': ('collapse',)
                }),
            )
        else:  # Modification d'un agent existant
            return (
                ('Informations personnelles', {
                    'fields': ('nom', 'prenoms', 'numero_carte_electeur', 'date_naissance', 'adresse', 'numero_telephone', 'email')
                }),
                ('Informations professionnelles', {
                    'fields': ('matricule', 'date_embauche', 'statut')
                }),
                ('Zone de responsabilité', {
                    'fields': ('region', 'prefecture')
                }),
                ('Compte utilisateur', {
                    'fields': ('utilisateur',),
                    'classes': ('collapse',),
                    'description': 'Le compte utilisateur associé à cet agent.'
                }),
                ('Statistiques', {
                    'fields': ('nombre_caisses', 'caisses_actives'),
                    'classes': ('collapse',)
                }),
                ('Dates', {
                    'fields': ('date_creation', 'date_derniere_activite'),
                    'classes': ('collapse',)
                }),
                ('Notes', {
                    'fields': ('notes',),
                    'classes': ('collapse',)
                }),
            )
    
    inlines = [CaisseInline]
    
    def get_form(self, request, obj=None, **kwargs):
        """Retourne le formulaire approprié selon le contexte"""
        if obj is None:  # Création d'un nouvel agent
            return AgentCreationForm
        return super().get_form(request, obj, **kwargs)
    
    def nom_complet(self, obj):
        return obj.nom_complet
    nom_complet.short_description = 'Nom Complet'
    
    def nombre_caisses(self, obj):
        return obj.nombre_caisses
    nombre_caisses.short_description = 'Nb Caisses'
    
    def caisses_actives(self, obj):
        return obj.caisses_actives
    caisses_actives.short_description = 'Caisses Actives'
    
    def save_model(self, request, obj, form, change):
        """Sauvegarde l'agent et crée automatiquement le compte utilisateur si demandé"""
        if not change:  # Création d'un nouvel agent
            # Sauvegarder d'abord l'agent
            super().save_model(request, obj, form, change)
            
            # Créer le compte utilisateur si demandé
            if form.cleaned_data.get('creer_compte_utilisateur', True):
                user_info = self._create_agent_user(obj, form, request)
                self._display_credentials(request, user_info, obj)
        else:
            # Modification d'un agent existant
            super().save_model(request, obj, form, change)
    
    def _create_agent_user(self, agent, form, request):
        """Crée un utilisateur pour un agent"""
        # Générer le nom d'utilisateur et mot de passe
        username = form.generate_username(agent.nom, agent.prenoms)
        password = form.generate_password()
        
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
        
        # Lier l'utilisateur à l'agent
        agent.utilisateur = user
        agent.save()
        
        # Créer un log d'audit
        AuditLog.objects.create(
            utilisateur=request.user,
            action='CREATION',
            modele='User',
            objet_id=user.id,
            details={
                'username': username,
                'password': password,
                'role': 'AGENT',
                'agent_matricule': agent.matricule,
                'auto_generated': True
            },
            ip_adresse=request.META.get('REMOTE_ADDR')
        )
        
        return {
            'user': user,
            'username': username,
            'password': password,
            'role': 'AGENT'
        }
    
    def _display_credentials(self, request, user_info, agent):
        """Affiche les informations de connexion générées et propose le téléchargement du PDF"""
        message = f"Agent créé avec succès! Voici les informations de connexion:\n\n"
        message += f"<strong>Agent:</strong> {agent.nom_complet}<br>"
        message += f"<strong>Matricule:</strong> {agent.matricule}<br><br>"
        message += f"<strong>Compte utilisateur:</strong><br>"
        message += f"Nom d'utilisateur: <code>{user_info['username']}</code><br>"
        message += f"Mot de passe: <code>{user_info['password']}</code><br><br>"
        message += "<strong>⚠️ IMPORTANT:</strong> Notez ces informations et communiquez-les à l'agent concerné.<br><br>"
        message += f"<a href='/adminsecurelogin/gestion_caisses/agent/{agent.id}/download-credentials/' class='button' style='background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;'>📄 Télécharger le PDF des identifiants</a>"
        
        messages.success(request, mark_safe(message))
        
        # Stocker les informations de l'utilisateur créé dans la session pour le PDF
        request.session['created_agent_data'] = {
            'username': user_info['username'],
            'password': user_info['password'],
            'agent_full_name': user_info['user'].get_full_name(),
            'matricule': agent.matricule,
            'numero_carte_electeur': agent.numero_carte_electeur
        }
    
    def has_add_permission(self, request):
        # Seuls les administrateurs peuvent créer des agents
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        # Seuls les administrateurs peuvent modifier des agents
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        # Seuls les administrateurs peuvent supprimer des agents
        if not request.user.is_superuser:
            return False
        
        # Empêcher la suppression si l'agent a des caisses
        if obj and obj.caisses.exists():
            return False
        
        return True
    
    def get_urls(self):
        """Ajoute les URLs personnalisées pour le téléchargement du PDF"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/download-credentials/',
                self.admin_site.admin_view(self.download_credentials),
                name='gestion_caisses_agent_download_credentials',
            ),
        ]
        return custom_urls + urls
    
    def download_credentials(self, request, object_id):
        """Télécharge le PDF des identifiants pour un agent"""
        try:
            agent = self.get_object(request, object_id)
            
            # Récupérer les données de l'agent créé depuis la session
            created_agent_data = request.session.get('created_agent_data', {})
            
            if not created_agent_data:
                messages.error(request, "Aucune donnée d'agent trouvée. Veuillez recréer l'agent.")
                return HttpResponseRedirect(reverse('admin:gestion_caisses_agent_change', args=[object_id]))
            
            # Créer l'objet utilisateur temporaire pour le PDF
            user = User()
            user.first_name = created_agent_data['agent_full_name'].split()[0] if created_agent_data['agent_full_name'] else ''
            user.last_name = ' '.join(created_agent_data['agent_full_name'].split()[1:]) if len(created_agent_data['agent_full_name'].split()) > 1 else ''
            
            created_user = {
                'user': user,
                'username': created_agent_data['username'],
                'password': created_agent_data['password'],
                'role': 'AGENT'
            }
            
            # Générer et retourner le PDF
            return create_agent_credentials_pdf_response(agent, created_user)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
            return HttpResponseRedirect(reverse('admin:gestion_caisses_agent_change', args=[object_id]))


@admin.register(Caisse)
class CaisseAdmin(AgentAdminMixin, admin.ModelAdmin):
    
    list_display = [
        'code', 'nom_association', 'region', 'prefecture', 'commune', 
        'statut', 'nombre_membres', 'fond_disponible', 'solde_disponible', 'date_creation'
    ]
    list_filter = ['statut', 'region', 'prefecture', 'commune', 'date_creation']
    search_fields = ['code', 'nom_association']
    ordering = ['-date_creation']
    list_per_page = 20
    def get_readonly_fields(self, request, obj=None):
        """Retourne les champs en lecture seule selon le contexte"""
        readonly = ['code', 'date_creation', 'nombre_membres', 'nombre_prets_actifs', 'solde_disponible']
        
        if obj is not None:  # Modification d'une caisse existante
            readonly.extend(['presidente', 'secretaire', 'tresoriere'])
        
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Retourne les fieldsets appropriés selon le contexte"""
        if obj is None:  # Création d'une nouvelle caisse
            return (
                ('Agent responsable', {
                    'fields': ('agent',),
                    'description': 'Sélectionnez l\'agent qui sera responsable de cette caisse'
                }),
                ('Informations générales', {
                    'fields': ('nom_association', 'description', 'notes')
                }),
                ('Localisation', {
                    'fields': ('region', 'prefecture', 'commune', 'canton', 'village')
                }),
                ('Statut et fonds', {
                    'fields': ('statut', 'fond_initial')
                }),
                ('Présidente', {
                    'fields': (
                        'presidente_nom', 'presidente_prenoms', 'presidente_numero_carte',
                        'presidente_date_naissance', 'presidente_adresse', 'presidente_telephone'
                    ),
                    'classes': ('wide',)
                }),
                ('Secrétaire', {
                    'fields': (
                        'secretaire_nom', 'secretaire_prenoms', 'secretaire_numero_carte',
                        'secretaire_date_naissance', 'secretaire_adresse', 'secretaire_telephone'
                    ),
                    'classes': ('wide',)
                }),
                ('Trésorière', {
                    'fields': (
                        'tresoriere_nom', 'tresoriere_prenoms', 'tresoriere_numero_carte',
                        'tresoriere_date_naissance', 'tresoriere_adresse', 'tresoriere_telephone'
                    ),
                    'classes': ('wide',)
                }),
            )
        else:  # Modification d'une caisse existante
            return (
                ('Agent responsable', {
                    'fields': ('agent',),
                    'description': 'Agent responsable de cette caisse'
                }),
                ('Informations générales', {
                    'fields': ('nom_association', 'description', 'notes')
                }),
                ('Localisation', {
                    'fields': ('region', 'prefecture', 'commune', 'canton', 'village')
                }),
                ('Statut et fonds', {
                    'fields': ('statut', 'fond_initial')
                }),
                ('Membres dirigeants (en lecture seule)', {
                    'fields': ('presidente', 'secretaire', 'tresoriere'),
                    'classes': ('collapse',),
                    'description': 'Les responsables ne peuvent pas être modifiés ici. Utilisez la gestion des membres pour les modifications.'
                }),
            )
    
    inlines = [MembreInline, PretInline]
    
    def get_form(self, request, obj=None, **kwargs):
        """Retourne le formulaire approprié selon le contexte"""
        if obj is None:  # Création d'une nouvelle caisse
            return CaisseCreationForm
        else:  # Modification d'une caisse existante
            return CaisseEditForm
    
    def nombre_membres(self, obj):
        return obj.nombre_membres
    nombre_membres.short_description = 'Nb Membres'
    
    def nombre_prets_actifs(self, obj):
        return obj.nombre_prets_actifs
    nombre_prets_actifs.short_description = 'Nb Prêts Actifs'
    
    def solde_disponible(self, obj):
        return obj.solde_disponible
    solde_disponible.short_description = 'Solde Disponible'
    
    def save_model(self, request, obj, form, change):
        """Sauvegarde la caisse et crée automatiquement les comptes utilisateurs pour les 3 responsables"""
        if not change:  # Création d'une nouvelle caisse
            # S'assurer que le fond initial est transféré vers le fond disponible
            if obj.fond_initial > 0:
                obj.fond_disponible = obj.fond_initial
            
            # Sauvegarder d'abord la caisse
            super().save_model(request, obj, form, change)
            
            # Créer les 3 membres responsables avec leurs comptes utilisateurs
            created_users = []
            
            # Créer la Présidente
            presidente_user = self._create_responsable_user(
                form.cleaned_data['presidente_nom'],
                form.cleaned_data['presidente_prenoms'],
                form.cleaned_data['presidente_numero_carte'],
                form.cleaned_data['presidente_date_naissance'],
                form.cleaned_data['presidente_adresse'],
                form.cleaned_data['presidente_telephone'],
                'PRESIDENTE',
                obj,
                form,
                request
            )
            created_users.append(presidente_user)
            
            # Créer la Secrétaire
            secretaire_user = self._create_responsable_user(
                form.cleaned_data['secretaire_nom'],
                form.cleaned_data['secretaire_prenoms'],
                form.cleaned_data['secretaire_numero_carte'],
                form.cleaned_data['secretaire_date_naissance'],
                form.cleaned_data['secretaire_adresse'],
                form.cleaned_data['secretaire_telephone'],
                'SECRETAIRE',
                obj,
                form,
                request
            )
            created_users.append(secretaire_user)
            
            # Créer la Trésorière
            tresoriere_user = self._create_responsable_user(
                form.cleaned_data['tresoriere_nom'],
                form.cleaned_data['tresoriere_prenoms'],
                form.cleaned_data['tresoriere_numero_carte'],
                form.cleaned_data['tresoriere_date_naissance'],
                form.cleaned_data['tresoriere_adresse'],
                form.cleaned_data['tresoriere_telephone'],
                'TRESORIERE',
                obj,
                form,
                request
            )
            created_users.append(tresoriere_user)
            
            # Mettre à jour les références dans la caisse
            obj.presidente = presidente_user['membre']
            obj.secretaire = secretaire_user['membre']
            obj.tresoriere = tresoriere_user['membre']
            obj.save()
            
            # Afficher les informations de connexion
            self._display_credentials(request, created_users, obj)
            
        else:
            # Modification d'une caisse existante
            super().save_model(request, obj, form, change)
    
    def _create_responsable_user(self, nom, prenoms, numero_carte, date_naissance, adresse, telephone, role, caisse, form, request):
        """Crée un utilisateur et un membre pour un responsable"""
        # Générer le nom d'utilisateur et mot de passe
        username = form.generate_username(nom, prenoms)
        password = form.generate_password()
        
        # Créer l'utilisateur
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=prenoms,
            last_name=nom,
            is_staff=False,
            is_superuser=False
        )
        
        # Créer le membre
        membre = Membre.objects.create(
            numero_carte_electeur=numero_carte,
            nom=nom,
            prenoms=prenoms,
            date_naissance=date_naissance,
            adresse=adresse,
            numero_telephone=telephone,
            role=role,
            statut='ACTIF',
            caisse=caisse,
            utilisateur=user
        )
        
        # Créer un log d'audit
        AuditLog.objects.create(
            utilisateur=request.user,
            action='CREATION',
            modele='User',
            objet_id=user.id,
            details={
                'username': username,
                'password': password,
                'role': role,
                'caisse': caisse.nom_association,
                'auto_generated': True
            },
            ip_adresse=request.META.get('REMOTE_ADDR')
        )
        
        return {
            'user': user,
            'membre': membre,
            'username': username,
            'password': password,
            'role': role
        }
    
    def _display_credentials(self, request, created_users, caisse):
        """Affiche les informations de connexion générées et propose le téléchargement du PDF"""
        message = "Caisse créée avec succès! Voici les informations de connexion des responsables:\n\n"
        
        for user_info in created_users:
            message += f"<strong>{user_info['role']}:</strong><br>"
            message += f"Nom d'utilisateur: <code>{user_info['username']}</code><br>"
            message += f"Mot de passe: <code>{user_info['password']}</code><br>"
            message += f"Nom complet: {user_info['user'].get_full_name()}<br><br>"
        
        message += "<strong>⚠️ IMPORTANT:</strong> Notez ces informations et communiquez-les aux responsables concernés.<br><br>"
        message += f"<a href='/adminsecurelogin/gestion_caisses/caisse/{caisse.id}/download-credentials/' class='button' style='background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;'>📄 Télécharger le PDF des identifiants</a>"
        
        messages.success(request, mark_safe(message))
        
        # Stocker les informations des utilisateurs créés dans la session pour le PDF
        request.session['created_users_data'] = [
            {
                'username': user_info['username'],
                'password': user_info['password'],
                'role': user_info['role'],
                'user_full_name': user_info['user'].get_full_name()
            }
            for user_info in created_users
        ]
    
    def has_add_permission(self, request):
        # Seuls les administrateurs peuvent créer des caisses
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        # Seuls les administrateurs peuvent modifier des caisses
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        # Seuls les administrateurs peuvent supprimer des caisses
        return request.user.is_superuser
    
    def get_urls(self):
        """Ajoute les URLs personnalisées pour le téléchargement du PDF"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/download-credentials/',
                self.admin_site.admin_view(self.download_credentials),
                name='gestion_caisses_caisse_download_credentials',
            ),
        ]
        return custom_urls + urls
    
    def download_credentials(self, request, object_id):
        """Télécharge le PDF des identifiants pour une caisse"""
        try:
            caisse = self.get_object(request, object_id)
            
            # Récupérer les données des utilisateurs créés depuis la session
            created_users_data = request.session.get('created_users_data', [])
            
            if not created_users_data:
                messages.error(request, "Aucune donnée d'utilisateur trouvée. Veuillez recréer la caisse.")
                return HttpResponseRedirect(reverse('admin:gestion_caisses_caisse_change', args=[object_id]))
            
            # Créer les objets utilisateur temporaires pour le PDF
            created_users = []
            for user_data in created_users_data:
                # Créer un objet User temporaire
                user = User()
                user.first_name = user_data['user_full_name'].split()[0] if user_data['user_full_name'] else ''
                user.last_name = ' '.join(user_data['user_full_name'].split()[1:]) if len(user_data['user_full_name'].split()) > 1 else ''
                
                created_users.append({
                    'user': user,
                    'username': user_data['username'],
                    'password': user_data['password'],
                    'role': user_data['role']
                })
            
            # Générer et retourner le PDF
            return create_credentials_pdf_response(caisse, created_users)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
            return HttpResponseRedirect(reverse('admin:gestion_caisses_caisse_change', args=[object_id]))


@admin.register(Membre)
class MembreAdmin(AgentAdminMixin, admin.ModelAdmin):
    list_display = [
        'numero_carte_electeur', 'nom_complet', 'role', 'statut', 
        'caisse', 'date_adhesion', 'numero_telephone'
    ]
    list_filter = ['role', 'statut', 'caisse__region', 'caisse__prefecture', 'caisse__commune', 'date_adhesion']
    search_fields = ['numero_carte_electeur', 'nom', 'prenoms', 'caisse__nom_association']
    ordering = ['nom', 'prenoms']
    list_per_page = 20
    readonly_fields = ['date_adhesion', 'date_derniere_activite']
    
    fieldsets = (
        ('Identification', {
            'fields': ('numero_carte_electeur', 'caisse')
        }),
        ('Informations personnelles', {
            'fields': ('nom', 'prenoms', 'date_naissance', 'adresse', 'numero_telephone', 'sexe', 'photo')
        }),
        ('Rôle et statut', {
            'fields': ('role', 'statut')
        }),
        ('Dates', {
            'fields': ('date_adhesion', 'date_derniere_activite'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def nom_complet(self, obj):
        return obj.nom_complet
    nom_complet.short_description = 'Nom Complet'
    
    def has_add_permission(self, request):
        # Seuls les administrateurs peuvent créer des membres
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        # Seuls les administrateurs peuvent modifier des membres
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        # Seuls les administrateurs peuvent supprimer des membres
        return request.user.is_superuser


# Dashboard d'administration principal
class AdminDashboard(CaisseAdmin):
    """Dashboard principal pour l'administrateur avec toutes les statistiques"""
    change_list_template = 'admin/gestion_caisses/dashboard/change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        """Vue personnalisée pour afficher le dashboard d'administration"""
        extra_context = extra_context or {}
        
        # Statistiques financières globales
        from django.db.models import Sum, Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculs des fonds totaux
        total_fonds_disponibles = Caisse.objects.aggregate(
            total=Sum('fond_disponible')
        )['total'] or 0
        
        total_fonds_initiaux = Caisse.objects.aggregate(
            total=Sum('fond_initial')
        )['total'] or 0
        
        total_fonds_rembourses = Caisse.objects.aggregate(
            total=Sum('montant_total_remboursements')
        )['total'] or 0
        
        # Statistiques des prêts
        total_prets = Pret.objects.count()
        prets_valides = Pret.objects.filter(statut='VALIDE').count()
        prets_en_cours = Pret.objects.filter(statut='EN_COURS').count()
        prets_rembourses = Pret.objects.filter(statut='REMBOURSE').count()
        prets_rejetes = Pret.objects.filter(statut='REJETE').count()
        
        # Montants des prêts
        total_montant_prets = Pret.objects.aggregate(
            total=Sum('montant_accord')
        )['total'] or 0
        
        total_montant_rembourse = Pret.objects.aggregate(
            total=Sum('montant_rembourse')
        )['total'] or 0
        
        # Calculer le montant restant en Python car c'est une propriété calculée
        total_montant_restant = total_montant_prets - total_montant_rembourse
        
        # Prêts en retard (échéances dépassées)
        today = timezone.now().date()
        prets_en_retard = Pret.objects.filter(
            echeances__date_echeance__lt=today,
            echeances__statut='EN_ATTENTE',
            statut__in=['VALIDE', 'EN_COURS']
        ).distinct().count()
        
        # Statistiques par région
        stats_par_region = Caisse.objects.values('region__nom').annotate(
            nombre_caisses=Count('id'),
            total_fonds=Sum('fond_disponible'),
            total_prets=Count('prets'),
            prets_actifs=Count('prets', filter=Q(prets__statut__in=['VALIDE', 'EN_COURS']))
        ).order_by('-total_fonds')
        
        # Statistiques par préfecture
        stats_par_prefecture = Caisse.objects.values('prefecture__nom').annotate(
            nombre_caisses=Count('id'),
            total_fonds=Sum('fond_disponible'),
            total_prets=Count('prets')
        ).order_by('-total_fonds')[:10]
        
        # Activité récente
        actions_recentes = AuditLog.objects.select_related('utilisateur').order_by('-date_action')[:10]
        
        # Graphiques des données (pour les graphiques JavaScript)
        # Utiliser une approche compatible avec SQLite
        from django.db.models.functions import ExtractMonth
        
        try:
            caisses_par_mois = Caisse.objects.annotate(
                month=ExtractMonth('date_creation')
            ).values('month').annotate(count=Count('id')).order_by('month')
        except:
            # Fallback pour SQLite si ExtractMonth ne fonctionne pas
            caisses_par_mois = []
        
        try:
            prets_par_mois = Pret.objects.annotate(
                month=ExtractMonth('date_demande')
            ).values('month').annotate(count=Count('id')).order_by('month')
        except:
            # Fallback pour SQLite si ExtractMonth ne fonctionne pas
            prets_par_mois = []
        
        extra_context.update({
            # Fonds et finances
            'total_fonds_disponibles': total_fonds_disponibles,
            'total_fonds_initiaux': total_fonds_initiaux,
            'total_fonds_rembourses': total_fonds_rembourses,
            'pourcentage_utilisation': (total_fonds_disponibles / total_fonds_initiaux * 100) if total_fonds_initiaux > 0 else 0,
            
            # Prêts
            'total_prets': total_prets,
            'prets_valides': prets_valides,
            'prets_en_cours': prets_en_cours,
            'prets_rembourses': prets_rembourses,
            'prets_rejetes': prets_rejetes,
            'prets_en_retard': prets_en_retard,
            
            # Montants
            'total_montant_prets': total_montant_prets,
            'total_montant_rembourse': total_montant_rembourse,
            'total_montant_restant': total_montant_restant,
            'taux_remboursement': (total_montant_rembourse / total_montant_prets * 100) if total_montant_prets > 0 else 0,
            
            # Statistiques géographiques
            'stats_par_region': stats_par_region,
            'stats_par_prefecture': stats_par_prefecture,
            
            # Activité
            'actions_recentes': actions_recentes,
            'caisses_par_mois': list(caisses_par_mois),
            'prets_par_mois': list(prets_par_mois),
            
            # Informations générales
            'nombre_caisses': Caisse.objects.count(),
            'nombre_agents': Agent.objects.count(),
            'nombre_membres': Membre.objects.count(),
        })
        
        return super().changelist_view(request, extra_context)

# Enregistrer le dashboard principal
# Remplacer l'ancien CaisseAdmin par le nouveau dashboard
admin.site.unregister(Caisse)
admin.site.register(Caisse, AdminDashboard)


# Les titres sont désormais définis dynamiquement dans apps.py via Parametre


@admin.register(PresidentGeneral)
class PresidentGeneralAdmin(admin.ModelAdmin):
    """Admin pour le Président Général"""
    list_display = ['nom_complet', 'numero_carte_electeur', 'statut', 'date_nomination']
    list_filter = ['statut', 'date_nomination']
    search_fields = ['nom', 'prenoms', 'numero_carte_electeur']
    readonly_fields = ['date_nomination']
    
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('nom', 'prenoms', 'numero_carte_electeur', 'date_naissance', 'adresse', 'numero_telephone')
        }),
        ('Documents', {
            'fields': ('photo', 'signature')
        }),
        ('Gestion', {
            'fields': ('statut', 'notes')
        }),
        ('Métadonnées', {
            'fields': ('date_nomination',),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """S'assurer qu'il n'y a qu'un seul président général actif"""
        if obj.statut == 'ACTIF':
            # Désactiver tous les autres présidents généraux
            PresidentGeneral.objects.exclude(pk=obj.pk).update(statut='INACTIF')
        super().save_model(request, obj, form, change)


@admin.register(Parametre)
class ParametreAdmin(admin.ModelAdmin):
    """Admin pour les paramètres de l'application"""
    list_display = ['nom_application', 'version_application', 'actif', 'date_modification']
    list_filter = ['actif', 'date_creation', 'date_modification']
    search_fields = ['nom_application', 'nom_president_general']
    readonly_fields = ['date_creation', 'date_modification']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('nom_application', 'logo', 'description_application', 'version_application')
        }),
        ('Contact', {
            'fields': ('telephone_principal', 'telephone_secondaire', 'email_contact', 'site_web')
        }),
        ('Adresse et siège social', {
            'fields': ('siege_social', 'adresse_postale', 'boite_postale', 'ville', 'pays')
        }),
        ('Président Général/PDG', {
            'fields': ('nom_president_general', 'titre_president_general', 'signature_president_general')
        }),
        ('Personnel', {
            'fields': ('nom_directeur_technique', 'nom_directeur_financier', 'nom_directeur_administratif')
        }),
        ('Informations légales', {
            'fields': ('numero_agrement', 'date_agrement', 'autorite_agrement', 'copyright_text', 'mentions_legales')
        }),
        ('Paramètres système', {
            'fields': ('devise', 'langue_par_defaut', 'fuseau_horaire')
        }),
        ('Gestion', {
            'fields': ('actif',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Permettre l'ajout seulement s'il n'y a pas déjà des paramètres actifs"""
        return not Parametre.objects.filter(actif=True).exists()
    
    def has_delete_permission(self, request, obj=None):
        """Empêcher la suppression des paramètres actifs"""
        if obj and obj.actif:
            return False
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """S'assurer qu'il n'y a qu'un seul ensemble de paramètres actifs"""
        if obj.actif:
            # Désactiver tous les autres paramètres
            Parametre.objects.exclude(pk=obj.pk).update(actif=False)
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Limiter l'affichage aux paramètres actifs pour les utilisateurs non-superuser"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(actif=True)
        return qs
