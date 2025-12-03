from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets, status, filters
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q, F, Prefetch
from django.utils import timezone
from datetime import datetime, timedelta, time
from types import SimpleNamespace
import json
from django.contrib.auth.models import User
from .models import (
    Region, Prefecture, Commune, Canton, Village, Quartier,
    Caisse, Membre, Pret, Echeance, MouvementFond, 
    VirementBancaire, AuditLog, Notification, Agent, CaisseGenerale, CaisseGeneraleMouvement,
    TransfertCaisse, SeanceReunion, Cotisation, Depense, RapportActivite,
    SalaireAgent, FichePaie, ExerciceCaisse
)
from .serializers import (
    RegionSerializer, PrefectureSerializer, CommuneSerializer, CantonSerializer, VillageSerializer, QuartierSerializer,
    CaisseSerializer, CaisseListSerializer, CaisseStatsSerializer,
    MembreSerializer, MembreListSerializer,
    PretSerializer, PretListSerializer,
    EcheanceSerializer, MouvementFondSerializer, VirementBancaireSerializer,
    AuditLogSerializer, NotificationSerializer, NotificationListSerializer, DashboardStatsSerializer,
    UserSerializer, CaisseGeneraleSerializer, CaisseGeneraleMouvementSerializer,
    TransfertCaisseSerializer, SeanceReunionSerializer, CotisationSerializer,
    DepenseSerializer, DepenseListSerializer, ExerciceCaisseSerializer,
    SalaireAgentSerializer, FichePaieSerializer, AgentListSerializer,
    serialize_exercice_info,
)
from .services import PretService, NotificationService
from .utils import (
    generate_pret_octroi_pdf,
    generate_remboursement_pdf,
    generate_remboursement_complet_pdf,
    generate_membres_liste_pdf,
    generate_membre_individual_pdf,
    generate_partage_fonds_pdf,
    get_parametres_application,
    generate_application_guide_pdf,
    generate_rapport_pdf,
    export_rapport_excel,
    export_rapport_csv,
)
from datetime import date
from .permissions import AgentPermissions
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from django.utils import timezone
import json
from datetime import datetime, timedelta


def ensure_caisse_has_active_exercice(caisse):
    """
    Vérifie qu'une caisse possède un exercice EN_COURS et actif.
    Lève une ValidationError sinon.
    """
    if not caisse:
        raise ValidationError({'caisse': "La caisse est obligatoire pour cette opération."})

    # Chercher un exercice EN_COURS pour cette caisse
    exercice = (
        ExerciceCaisse.objects
        .filter(caisse=caisse, statut='EN_COURS')
        .order_by('-date_debut')
        .first()
    )

    if not exercice or not exercice.est_actif:
        raise ValidationError({
            'detail': (
                "Aucun exercice en cours pour cette caisse. "
                "Veuillez ouvrir un exercice avant d'enregistrer des opérations."
            )
        })

    return exercice
# ============================================================================
# Bloc utilitaire: synthèse "Caisse Générale" pour les rapports
# ============================================================================

def _build_caisse_generale_block(date_debut=None, date_fin=None):
    """Construit le bloc de synthèse pour la Caisse Générale.

    Contenu:
    - soldes: réserve, total caisses, système
    - mouvements de la caisse générale (agrégés par type) sur la période
    - derniers mouvements (limités) pour contexte
    """
    from django.db.models import Sum, Count, Q
    from .models import CaisseGenerale, CaisseGeneraleMouvement

    cg = CaisseGenerale.get_instance()

    from django.utils import timezone
    # Construire des bornes timezone-aware pour les DateTimeField
    start_dt = None
    end_dt = None
    if date_debut:
        start_dt = timezone.make_aware(datetime.combine(date_debut, time.min), timezone.get_current_timezone())
    if date_fin:
        end_dt = timezone.make_aware(datetime.combine(date_fin, time.max), timezone.get_current_timezone())

    filtres_date = Q()
    if start_dt:
        filtres_date &= Q(date_mouvement__gte=start_dt)
    if end_dt:
        filtres_date &= Q(date_mouvement__lte=end_dt)

    mv_qs = CaisseGeneraleMouvement.objects.filter(filtres_date).order_by('-date_mouvement')
    mv_stats = list(
        mv_qs.values('type_mouvement').annotate(total=Sum('montant'), nombre=Count('id'))
    )

    derniers = [
        {
            'date': m.date_mouvement.strftime('%d/%m/%Y'),
            'type': m.type_mouvement,
            'montant': float(m.montant),
            'description': m.description,
            'caisse_destination': m.caisse_destination.nom_association if m.caisse_destination else None,
        }
        for m in mv_qs[:10]
    ]

    return {
        'soldes': {
            'solde_reserve': float(cg.solde_reserve or 0),
            'solde_total_caisses': float(cg.solde_total_caisses or 0),
            'solde_systeme': float(cg.solde_systeme or 0),
        },
        'mouvements': {
            'par_type': mv_stats,
            'derniers': derniers,
        }
    }

import os
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum, Count, Q, F, Prefetch, Case, When
from django.db.models.functions import TruncMonth, TruncDate


def get_user_caisse(user):
    """Retourne la caisse liée au profil de l'utilisateur (None si non liée).
    Pour les agents, retourne None (utiliser get_user_caisses pour obtenir toutes leurs caisses)."""
    if user.is_superuser:
        return None  # Les admins voient toutes les caisses
    
    # Vérifier si c'est un agent
    if AgentPermissions.is_agent(user):
        return None  # Les agents ont plusieurs caisses, utiliser get_user_caisses
    
    # Sinon, vérifier si c'est un membre
    profil = getattr(user, 'profil_membre', None)
    return getattr(profil, 'caisse', None) if profil else None


def get_user_caisses(user):
    """Retourne la liste des caisses accessibles par l'utilisateur.
    - Pour les admins: toutes les caisses
    - Pour les agents: toutes leurs caisses assignées
    - Pour les membres: uniquement leur caisse
    - Sinon: liste vide"""
    if user.is_superuser:
        return Caisse.objects.all()
    
    # Vérifier si c'est un agent
    if AgentPermissions.is_agent(user):
        return AgentPermissions.get_agent_caisses(user)
    
    # Sinon, vérifier si c'est un membre
    caisse = get_user_caisse(user)
    if caisse:
        return Caisse.objects.filter(id=caisse.id)
    
    return Caisse.objects.none()


# API: Séances de réunion
class SeanceReunionViewSet(viewsets.ModelViewSet):
    queryset = SeanceReunion.objects.select_related('caisse').all()
    serializer_class = SeanceReunionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['caisse', 'date_seance']
    search_fields = ['titre', 'caisse__nom_association']
    ordering_fields = ['date_seance', 'date_creation']
    ordering = ['-date_seance']
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs


# API: Cotisations
class CotisationViewSet(viewsets.ModelViewSet):
    queryset = Cotisation.objects.select_related('caisse', 'membre', 'seance').all()
    serializer_class = CotisationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['caisse', 'membre', 'seance']
    search_fields = ['membre__nom', 'membre__prenoms', 'caisse__nom_association']
    ordering_fields = ['date_cotisation', 'montant_total']
    ordering = ['-date_cotisation']
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs

    def perform_create(self, serializer):
        """
        Création de cotisation : interdite si la caisse n'a pas d'exercice EN_COURS.
        """
        caisse = serializer.validated_data.get('caisse')
        caisse_id = serializer.validated_data.get('caisse_id')
        if not caisse and caisse_id:
            try:
                caisse = Caisse.objects.get(pk=caisse_id)
                serializer.validated_data['caisse'] = caisse
            except Caisse.DoesNotExist:
                raise ValidationError({'caisse_id': "Caisse introuvable."})
        if not caisse:
            raise ValidationError({'caisse': "La caisse est obligatoire pour enregistrer une cotisation."})

        # Vérifier l'existence d'un exercice en cours pour cette caisse
        ensure_caisse_has_active_exercice(caisse)

        serializer.save(utilisateur=self.request.user)


# API: Statistiques des cotisations
class CotisationStatsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='caisse')
    def caisse_stats(self, request):
        """Totaux des cotisations pour une caisse, avec options de période et groupement mensuel.

        Params:
        - caisse_id (obligatoire)
        - debut (YYYY-MM-DD, optionnel)
        - fin (YYYY-MM-DD, optionnel)
        - group_by=month (optionnel)
        """
        caisse_id = request.query_params.get('caisse_id')
        if not caisse_id:
            raise ValidationError({'caisse_id': 'Paramètre requis'})

        qs = Cotisation.objects.filter(caisse_id=caisse_id)

        # Filtre période
        debut = request.query_params.get('debut')
        fin = request.query_params.get('fin')
        if debut:
            try:
                debut_dt = datetime.strptime(debut, '%Y-%m-%d')
                qs = qs.filter(date_cotisation__date__gte=debut_dt.date())
            except Exception:
                raise ValidationError({'debut': 'Format attendu YYYY-MM-DD'})
        if fin:
            try:
                fin_dt = datetime.strptime(fin, '%Y-%m-%d')
                qs = qs.filter(date_cotisation__date__lte=fin_dt.date())
            except Exception:
                raise ValidationError({'fin': 'Format attendu YYYY-MM-DD'})

        # Groupement
        if request.query_params.get('group_by') == 'month':
            data = list(
                qs.annotate(mois=TruncMonth('date_cotisation'))
                  .values('mois')
                  .annotate(
                      total=Sum('montant_total'),
                      prix_tempon=Sum('prix_tempon'),
                      frais_solidarite=Sum('frais_solidarite'),
                      frais_fondation=Sum('frais_fondation'),
                      penalite_emprunt_retard=Sum('penalite_emprunt_retard'),
                      nombre=Count('id')
                  )
                  .order_by('mois')
            )
            # Sérialiser mois en str
            for item in data:
                item['mois'] = item['mois'].strftime('%Y-%m') if item['mois'] else None
            return Response({'caisse_id': int(caisse_id), 'group_by': 'month', 'series': data})

        # Totaux simples
        agg = qs.aggregate(
            total=Sum('montant_total') or 0,
            prix_tempon=Sum('prix_tempon') or 0,
            frais_solidarite=Sum('frais_solidarite') or 0,
            frais_fondation=Sum('frais_fondation') or 0,
            penalite_emprunt_retard=Sum('penalite_emprunt_retard') or 0,
            nombre=Count('id')
        )
        return Response({'caisse_id': int(caisse_id), 'totaux': agg})

    @action(detail=False, methods=['get'], url_path='seance')
    def seance_stats(self, request):
        """Totaux des cotisations pour une séance donnée.

        Params: seance_id (obligatoire)
        """
        seance_id = request.query_params.get('seance_id')
        if not seance_id:
            raise ValidationError({'seance_id': 'Paramètre requis'})
        qs = Cotisation.objects.filter(seance_id=seance_id)
        agg = qs.aggregate(
            total=Sum('montant_total') or 0,
            prix_tempon=Sum('prix_tempon') or 0,
            frais_solidarite=Sum('frais_solidarite') or 0,
            frais_fondation=Sum('frais_fondation') or 0,
            penalite_emprunt_retard=Sum('penalite_emprunt_retard') or 0,
            nombre=Count('id')
        )
        return Response({'seance_id': int(seance_id), 'totaux': agg})

    @action(detail=False, methods=['get'], url_path='membre')
    def membre_stats(self, request):
        """Totaux et séries de cotisations pour un membre.

        Params:
        - membre_id (obligatoire)
        - debut (YYYY-MM-DD, optionnel)
        - fin (YYYY-MM-DD, optionnel)
        """
        membre_id = request.query_params.get('membre_id')
        if not membre_id:
            raise ValidationError({'membre_id': 'Paramètre requis'})

        qs = Cotisation.objects.filter(membre_id=membre_id)

        # Filtre période
        debut = request.query_params.get('debut')
        fin = request.query_params.get('fin')
        if debut:
            try:
                debut_dt = datetime.strptime(debut, '%Y-%m-%d')
                qs = qs.filter(date_cotisation__date__gte=debut_dt.date())
            except Exception:
                raise ValidationError({'debut': 'Format attendu YYYY-MM-DD'})
        if fin:
            try:
                fin_dt = datetime.strptime(fin, '%Y-%m-%d')
                qs = qs.filter(date_cotisation__date__lte=fin_dt.date())
            except Exception:
                raise ValidationError({'fin': 'Format attendu YYYY-MM-DD'})

        # Nombre de mois distincts cotisés
        mois_count = qs.annotate(mois=TruncMonth('date_cotisation')).values('mois').distinct().count()

        if request.query_params.get('group_by') == 'month':
            data = list(
                qs.annotate(mois=TruncMonth('date_cotisation'))
                  .values('mois')
                  .annotate(
                      total=Sum('montant_total'),
                      prix_tempon=Sum('prix_tempon'),
                      frais_solidarite=Sum('frais_solidarite'),
                      frais_fondation=Sum('frais_fondation'),
                      penalite_emprunt_retard=Sum('penalite_emprunt_retard'),
                      nombre=Count('id')
                  )
                  .order_by('mois')
            )
            for item in data:
                item['mois'] = item['mois'].strftime('%Y-%m') if item['mois'] else None
            return Response({'membre_id': int(membre_id), 'group_by': 'month', 'nombre_mois_cotises': mois_count, 'series': data})

        agg = qs.aggregate(
            total=Sum('montant_total') or 0,
            prix_tempon=Sum('prix_tempon') or 0,
            frais_solidarite=Sum('frais_solidarite') or 0,
            frais_fondation=Sum('frais_fondation') or 0,
            penalite_emprunt_retard=Sum('penalite_emprunt_retard') or 0,
            nombre=Count('id')
        )
        return Response({'membre_id': int(membre_id), 'nombre_mois_cotises': mois_count, 'totaux': agg})

# Contexte utilisateur pour le frontend
@login_required
def user_context(request):
    """Retourne la caisse et le rôle de l'utilisateur connecté"""
    user = request.user
    role = get_user_role(user)
    
    # Pour les agents, on retourne toutes leurs caisses et la première par défaut
    # Pour les membres, on retourne leur caisse unique
    caisse_id = None
    caisse_code = None
    caisses = []
    
    if role == 'Agent':
        # Pour les agents, retourner toutes leurs caisses
        agent_caisses = AgentPermissions.get_agent_caisses(user)
        caisses = [
            {
                'id': caisse.id,
                'code': caisse.code,
                'nom_association': caisse.nom_association,
                'statut': caisse.statut
            }
            for caisse in agent_caisses
        ]
        # Retourner la première caisse par défaut (ou None si aucune)
        if agent_caisses.exists():
            first_caisse = agent_caisses.first()
            caisse_id = first_caisse.id
            caisse_code = first_caisse.code
    elif role != 'Administrateur':
        # Pour les membres
        profil = getattr(user, 'profil_membre', None)
        if profil and profil.caisse:
            caisse_id = profil.caisse.id
            caisse_code = profil.caisse.code
            caisses = [{
                'id': profil.caisse.id,
                'code': profil.caisse.code,
                'nom_association': profil.caisse.nom_association,
                'statut': profil.caisse.statut
            }]
    
    return JsonResponse({
        'user': {
            'id': user.id,
            'username': user.username,
            'role': role,
        },
        'caisse_id': caisse_id,
        'caisse_code': caisse_code,
        'caisses': caisses,  # Liste des caisses accessibles (utile pour les agents)
    })

# Vue pour le frontend principal
def index_view(request):
    """Vue principale qui sert la page de connexion personnalisée ou redirige si connecté"""
    if request.user.is_authenticated:
        # Rediriger les administrateurs vers l'admin Django sécurisé
        if request.user.is_superuser and request.user.username == 'admin':
            return redirect('/adminsecurelogin/')
        # Rediriger tous les autres vers le dashboard frontend
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    context = {
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/login.html', context)

def login_view(request):
    """Route explicite pour la page de connexion"""
    if request.user.is_authenticated:
        # Rediriger les administrateurs vers l'admin Django sécurisé
        if request.user.is_superuser and request.user.username == 'admin':
            return redirect('/adminsecurelogin/')
        # Rediriger tous les autres vers le dashboard frontend
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    context = {
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/login.html', context)

# Vue pour le dashboard après connexion
@login_required
def dashboard_view(request):
    """Vue du dashboard principal après connexion"""
    # Rediriger seulement les administrateurs vers l'admin Django sécurisé
    if request.user.is_superuser and request.user.username == 'admin':
        return redirect('/adminsecurelogin/')
    
    # Pour tous les autres utilisateurs (agents, présidente, secrétaire, trésorière, membres)
    # rester dans le frontend
    user_role = get_user_role(request.user)
    caisse_nom = ''
    
    if user_role == 'Agent':
        # Pour les agents, prendre la première caisse ou laisser vide
        agent_caisses = AgentPermissions.get_agent_caisses(request.user)
        if agent_caisses.exists():
            caisse_nom = agent_caisses.first().nom_association
    else:
        user_caisse = get_user_caisse(request.user)
        caisse_nom = user_caisse.nom_association if user_caisse else ''
    
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    
    context = {
        'user': request.user,
        'user_role': user_role,
        'caisse_nom': caisse_nom,
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/dashboard.html', context)

# Vue pour la gestion des caisses
@login_required
def caisses_view(request):
    """Vue pour la gestion des caisses"""
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    
    context = {
        'user': request.user,
        'user_role': get_user_role(request.user),
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/caisses.html', context)

# Vue pour la gestion des membres
@login_required
def membres_view(request):
    """Vue pour la gestion des membres"""
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    
    # Charger une liste complète pour affichage (limite raisonnable)
    membres_full = Membre.objects.select_related('caisse').all().order_by('caisse__nom_association','nom','prenoms')[:1000]
    from .serializers import MembreListSerializer
    membres_data = MembreListSerializer(membres_full, many=True).data

    context = {
        'user': request.user,
        'user_role': get_user_role(request.user),
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
        'details_membres_full': membres_data,
    }
    return render(request, 'gestion_caisses/membres.html', context)

# Vue pour la gestion des prêts
@login_required
def prets_view(request):
    """Vue pour la gestion des prêts"""
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    
    context = {
        'user': request.user,
        'user_role': get_user_role(request.user),
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/prets.html', context)

# Vue pour la gestion des utilisateurs (réservée aux administrateurs)
@login_required
def users_view(request):
    """Vue pour la gestion des utilisateurs (réservée aux administrateurs)"""
    if not request.user.is_superuser:
        return redirect('/gestion-caisses/dashboard/')
    
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    
    context = {
        'user': request.user,
        'user_role': get_user_role(request.user),
        'nom_application': parametres['nom_application'],
        'logo': parametres['logo'],
        'description_application': parametres['description_application'],
    }
    return render(request, 'gestion_caisses/users.html', context)

# API pour l'authentification
@require_http_methods(["POST"])
def api_login(request):
    """API endpoint pour la connexion"""
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return JsonResponse({
                'success': False,
                'message': 'Nom d\'utilisateur et mot de passe requis'
            }, status=400)
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Connexion réussie',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': get_user_role(user)
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Nom d\'utilisateur ou mot de passe incorrect'
            }, status=401)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Données JSON invalides'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def api_logout(request):
    """API endpoint pour la déconnexion"""
    logout(request)
    return JsonResponse({
        'success': True,
        'message': 'Déconnexion réussie'
    })

# Fonction utilitaire pour déterminer le rôle de l'utilisateur
def get_user_role(user):
    """Détermine le rôle de l'utilisateur basé sur son profil membre ou agent"""
    if user.is_superuser:
        return 'Administrateur'
    
    # Vérifier si l'utilisateur est un agent
    if AgentPermissions.is_agent(user):
        return 'Agent'
    
    # Vérifier si l'utilisateur a un profil membre
    try:
        membre = user.profil_membre
        if membre:
            # Retourner le rôle spécifique du membre
            role_mapping = {
                'PRESIDENTE': 'Présidente',
                'SECRETAIRE': 'Secrétaire',
                'TRESORIERE': 'Trésorière',
                'MEMBRE': 'Membre'
            }
            return role_mapping.get(membre.role, 'Membre')
    except:
        pass
    
    # Fallback pour les utilisateurs sans profil membre
    return 'Membre'


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la gestion des régions (lecture seule)"""
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'code']
    ordering = ['nom']


class PrefectureViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la gestion des préfectures (lecture seule)"""
    queryset = Prefecture.objects.select_related('region').all()
    serializer_class = PrefectureSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['region']
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'code']
    ordering = ['nom']


class CommuneViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la gestion des communes (lecture seule)"""
    queryset = Commune.objects.select_related('prefecture', 'prefecture__region').all()
    serializer_class = CommuneSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['prefecture', 'prefecture__region']
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'code']
    ordering = ['nom']


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    """Liste en lecture seule des agents pour les formulaires"""
    queryset = Agent.objects.all().order_by('nom', 'prenoms')
    serializer_class = AgentListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom', 'prenoms', 'matricule']


class CantonViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la gestion des cantons (lecture seule)"""
    queryset = Canton.objects.select_related('commune', 'commune__prefecture').all()
    serializer_class = CantonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['commune', 'commune__prefecture']
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'code']
    ordering = ['nom']


class VillageViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la gestion des villages (lecture seule)"""
    queryset = Village.objects.select_related('canton', 'canton__commune').all()
    serializer_class = VillageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['canton', 'canton__commune']
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'code']
    ordering = ['nom']


class QuartierViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la gestion des quartiers (lecture seule)"""
    queryset = Quartier.objects.select_related('village', 'village__canton', 'village__canton__commune').all()
    serializer_class = QuartierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['village', 'village__canton']
    search_fields = ['nom', 'code']
    ordering_fields = ['nom', 'code']
    ordering = ['nom']

class CaisseViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des caisses"""
    queryset = Caisse.objects.select_related(
        'region', 'prefecture', 'commune', 'canton', 'village',
        'agent', 'presidente', 'secretaire', 'tresoriere'
    ).prefetch_related(
        'membres',
        Prefetch('exercices', queryset=ExerciceCaisse.objects.filter(statut='EN_COURS').order_by('-date_debut'))
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'region', 'prefecture', 'commune']
    search_fields = ['nom_association', 'code']
    ordering_fields = ['nom_association', 'date_creation', 'fond_disponible']
    ordering = ['-date_creation']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CaisseListSerializer
        elif self.action == 'stats':
            return CaisseStatsSerializer
        return CaisseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Les non-admins voient uniquement leurs caisses (membre) ou les caisses assignées (agent)
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(id__in=user_caisses.values_list('id', flat=True))
            else:
                qs = qs.none()
        return qs
    
    def perform_create(self, serializer):
        caisse = serializer.save()
        # Log de création
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='CREATION',
            modele='Caisse',
            objet_id=caisse.id,
            details={'nom_association': caisse.nom_association, 'code': caisse.code},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
    
    def perform_update(self, serializer):
        caisse = serializer.save()
        # Log de modification
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='MODIFICATION',
            modele='Caisse',
            objet_id=caisse.id,
            details={'nom_association': caisse.nom_association, 'code': caisse.code},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Obtenir les statistiques d'une caisse spécifique"""
        caisse = self.get_object()
        serializer = self.get_serializer(caisse)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def total_stats(self, request):
        """Obtenir les statistiques globales des caisses"""
        total_caisses = Caisse.objects.count()
        total_caisses_actives = Caisse.objects.filter(statut='ACTIVE').count()
        total_fond_disponible = Caisse.objects.aggregate(
            total=Sum('fond_disponible')
        )['total'] or 0
        
        return Response({
            'total_caisses': total_caisses,
            'total_caisses_actives': total_caisses_actives,
            'total_fond_disponible': total_fond_disponible,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def ouvrir_exercice(self, request, pk=None):
        """Admin: ouvrir un exercice (12 mois) pour une caisse donnée.

        Input JSON: { "date_debut": "YYYY-MM-DD", "notes": "..." }
        """
        caisse = self.get_object()
        date_debut_str = request.data.get('date_debut')
        notes = request.data.get('notes', '')

        if not date_debut_str:
            raise ValidationError({'date_debut': 'Champ requis (YYYY-MM-DD).'})

        try:
            from datetime import datetime
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
        except Exception:
            raise ValidationError({'date_debut': 'Format invalide. Utilisez YYYY-MM-DD.'})

        # Empêcher deux exercices en cours
        if ExerciceCaisse.objects.filter(caisse=caisse, statut='EN_COURS').exists():
            raise ValidationError({'detail': 'Un exercice est déjà en cours pour cette caisse.'})

        # Calculer le total des frais de fondation de toutes les cotisations de la caisse
        from decimal import Decimal
        from django.db.models import Sum
        total_frais_fondation = (
            Cotisation.objects
            .filter(caisse=caisse)
            .aggregate(total=Sum('frais_fondation'))['total'] or Decimal('0')
        )

        # Sauvegarder les valeurs avant modification pour l'audit
        fond_initial_avant = caisse.fond_initial
        fond_disponible_avant = caisse.fond_disponible

        # Réinitialiser les comptes de la caisse
        # fond_initial = 0
        # fond_disponible = total des frais de fondation (conservés)
        # Utiliser update() pour éviter la logique automatique de save()
        Caisse.objects.filter(pk=caisse.pk).update(
            fond_initial=Decimal('0'),
            fond_disponible=total_frais_fondation
        )
        # Recharger l'objet depuis la base de données
        caisse.refresh_from_db()

        # Mettre à jour la CaisseGenerale si elle existe
        try:
            caisse_generale = CaisseGenerale.get_instance()
            caisse_generale.recalculer_total_caisses()
        except Exception:
            # Ne pas bloquer si la caisse générale n'existe pas ou erreur
            pass

        exercice = ExerciceCaisse.objects.create(
            caisse=caisse,
            date_debut=date_debut,
            notes=notes,
        )

        # Log d'audit pour la création de l'exercice
        AuditLog.objects.create(
            utilisateur=request.user,
            action='CREATION',
            modele='ExerciceCaisse',
            objet_id=exercice.id,
            details={
                'caisse': caisse.nom_association,
                'date_debut': str(exercice.date_debut),
                'date_fin': str(exercice.date_fin),
                'reinitialisation_comptes': True,
                'fond_initial_avant': str(fond_initial_avant),
                'fond_disponible_avant': str(fond_disponible_avant),
                'fond_initial_apres': '0',
                'fond_disponible_apres': str(total_frais_fondation),
                'frais_fondation_conserves': str(total_frais_fondation)
            },
            ip_adresse=request.META.get('REMOTE_ADDR')
        )

        return Response(ExerciceCaisseSerializer(exercice).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def cloturer_exercice(self, request, pk=None):
        """Admin: clôturer l'exercice en cours pour une caisse.

        Optionnel: { "date_fin": "YYYY-MM-DD" } sinon garde la date calculée.
        """
        caisse = self.get_object()
        exercice = ExerciceCaisse.objects.filter(caisse=caisse, statut='EN_COURS').order_by('-date_debut').first()
        if not exercice:
            raise ValidationError({'detail': "Aucun exercice en cours pour cette caisse."})

        date_fin_str = request.data.get('date_fin')
        if date_fin_str:
            try:
                from datetime import datetime
                date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
                exercice.date_fin = date_fin
            except Exception:
                raise ValidationError({'date_fin': 'Format invalide. Utilisez YYYY-MM-DD.'})

        exercice.statut = 'CLOTURE'
        exercice.save()

        AuditLog.objects.create(
            utilisateur=request.user,
            action='MODIFICATION',
            modele='ExerciceCaisse',
            objet_id=exercice.id,
            details={'caisse': caisse.nom_association, 'statut': 'CLOTURE', 'date_fin': str(exercice.date_fin)},
            ip_adresse=request.META.get('REMOTE_ADDR')
        )

        return Response(ExerciceCaisseSerializer(exercice).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def archiver_exercice(self, request, pk=None):
        """Admin: archiver l'exercice en cours ou récemment clôturé de la caisse.

        Crée une `ExerciceArchive` avec un snapshot des indicateurs clés et retourne l'archive.
        """
        caisse = self.get_object()
        exercice = ExerciceCaisse.objects.filter(caisse=caisse, statut='EN_COURS').order_by('-date_debut').first()
        if not exercice:
            exercice = ExerciceCaisse.objects.filter(caisse=caisse, statut='CLOTURE').order_by('-date_fin', '-date_debut').first()
        if not exercice:
            raise ValidationError({'detail': "Aucun exercice à archiver pour cette caisse."})

        # Si en cours, clore automatiquement avec la date_fin si absente
        if exercice.statut == 'EN_COURS' and not exercice.date_fin:
            from .models import add_months_to_date
            exercice.date_fin = add_months_to_date(exercice.date_debut, 12)
            exercice.statut = 'CLOTURE'
            exercice.save()

        # Snapshot indicateurs
        totaux_cot = Cotisation.objects.filter(
            caisse=caisse,
            date_cotisation__date__gte=exercice.date_debut,
            date_cotisation__date__lte=exercice.date_fin
        ).aggregate(total=Sum('montant_total'), nombre=Count('id'))
        totaux_prets = Pret.objects.filter(
            caisse=caisse,
            date_demande__date__gte=exercice.date_debut,
            date_demande__date__lte=exercice.date_fin
        ).aggregate(nombre=Count('id'))
        snapshot = {
            'cotisations': {
                'total': float(totaux_cot['total'] or 0),
                'nombre': int(totaux_cot['nombre'] or 0),
            },
            'prets': {
                'nombre': int(totaux_prets['nombre'] or 0),
            },
            'solde_caisse_fin': float(caisse.fond_disponible or 0),
        }

        from .models import ExerciceArchive
        archive, created = ExerciceArchive.objects.get_or_create(
            exercice=exercice,
            defaults={
                'caisse': caisse,
                'date_debut': exercice.date_debut,
                'date_fin': exercice.date_fin,
                'archived_by': request.user,
                'snapshot': snapshot,
                'notes': request.data.get('notes', ''),
            }
        )

        AuditLog.objects.create(
            utilisateur=request.user,
            action='ARCHIVE',
            modele='ExerciceArchive',
            objet_id=archive.id,
            details={'caisse': caisse.nom_association, 'exercice_id': exercice.id},
            ip_adresse=request.META.get('REMOTE_ADDR')
        )

        return Response({'archive_id': archive.id, 'snapshot': archive.snapshot, 'date_debut': str(archive.date_debut), 'date_fin': str(archive.date_fin)}, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def membres_liste_pdf(self, request, pk=None):
        """Télécharger le PDF de la liste des membres d'une caisse"""
        caisse = self.get_object()
        pdf = generate_membres_liste_pdf(caisse)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=liste_membres_{caisse.code}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return response
    
    @action(detail=True, methods=['get'])
    def echeances_retard_pdf(self, request, pk=None):
        """Télécharger le PDF des échéances en retard d'une caisse"""
        caisse = self.get_object()
        from .echeances_utils import generate_echeances_retard_pdf
        pdf = generate_echeances_retard_pdf(caisse)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=echeances_retard_{caisse.code}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return response
    
    @action(detail=False, methods=['get'])
    def echeances_retard_global_pdf(self, request):
        """Télécharger le PDF des échéances en retard pour toutes les caisses (admin seulement)"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission refusée. Seuls les administrateurs peuvent accéder à ce rapport.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from .echeances_utils import generate_echeances_retard_pdf
        pdf = generate_echeances_retard_pdf()  # Sans caisse spécifique
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=echeances_retard_global_{datetime.now().strftime('%Y%m%d')}.pdf"
        return response


class MembreViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des membres"""
    queryset = Membre.objects.select_related('caisse').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'role', 'caisse']
    search_fields = ['nom', 'prenoms', 'numero_carte_electeur']
    ordering_fields = ['nom', 'prenoms', 'date_adhesion']
    ordering = ['nom', 'prenoms']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MembreListSerializer
        return MembreSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses (membre ou agent)
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs
    
    def perform_create(self, serializer):
        # Vérifier les restrictions sur les rôles
        role = serializer.validated_data.get('role', 'MEMBRE')
        
        # Seuls les administrateurs peuvent créer des membres clés (président, secrétaire, trésorier)
        if role in ['PRESIDENTE', 'SECRETAIRE', 'TRESORIERE'] and not self.request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent créer des présidents, secrétaires et trésoriers.'})
        
        # Pour les non-admins, vérifier que la caisse appartient à l'utilisateur
        if not self.request.user.is_superuser:
            caisse = serializer.validated_data.get('caisse')
            user_caisses = get_user_caisses(self.request.user)
            
            # Si c'est un membre (une seule caisse), utiliser automatiquement sa caisse
            if not AgentPermissions.is_agent(self.request.user):
                caisse = get_user_caisse(self.request.user)
                if not caisse:
                    raise ValidationError({'detail': 'Aucune caisse associée à votre compte.'})
            
            # Vérifier que la caisse sélectionnée appartient à l'utilisateur
            if caisse not in user_caisses:
                raise ValidationError({'detail': 'Vous n\'avez pas accès à cette caisse.'})
            
            # Respecter la limite de 30 actifs
            if caisse and caisse.membres.filter(statut='ACTIF').count() >= 30 and serializer.validated_data.get('statut', 'ACTIF') == 'ACTIF':
                raise ValidationError({'detail': 'Une caisse ne peut pas avoir plus de 30 membres actifs.'})
            membre = serializer.save(caisse=caisse)
        else:
            membre = serializer.save()

    def perform_update(self, serializer):
        # Vérifier les restrictions sur les rôles
        role = serializer.validated_data.get('role', serializer.instance.role)
        
        # Seuls les administrateurs peuvent modifier les rôles clés (président, secrétaire, trésorier)
        if role in ['PRESIDENTE', 'SECRETAIRE', 'TRESORIERE'] and not self.request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent modifier les rôles de président, secrétaire et trésorier.'})
        
        if not self.request.user.is_superuser:
            # Vérifier que la caisse du membre appartient à l'utilisateur
            caisse = serializer.instance.caisse
            user_caisses = get_user_caisses(self.request.user)
            
            if caisse not in user_caisses:
                raise ValidationError({'detail': 'Vous n\'avez pas accès à cette caisse.'})
            
            # Permettre de changer la caisse seulement pour les agents (dans leurs caisses)
            new_caisse = serializer.validated_data.get('caisse', caisse)
            if AgentPermissions.is_agent(self.request.user) and new_caisse and new_caisse != caisse:
                if new_caisse not in user_caisses:
                    raise ValidationError({'detail': 'Vous n\'avez pas accès à cette caisse.'})
                caisse = new_caisse
            
            statut_nouveau = serializer.validated_data.get('statut')
            # Si on active un membre et qu'on atteint la limite
            if statut_nouveau == 'ACTIF' and caisse and caisse.membres.filter(statut='ACTIF').exclude(pk=serializer.instance.pk).count() >= 30:
                raise ValidationError({'detail': 'Limite de 30 membres actifs atteinte pour cette caisse.'})
            serializer.save(caisse=caisse)
        else:
            serializer.save()
        # Log de modification
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='MODIFICATION',
            modele='Membre',
            objet_id=serializer.instance.id,
            details={'nom': serializer.instance.nom, 'prenoms': serializer.instance.prenoms, 'caisse': serializer.instance.caisse.nom_association},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
    
    @action(detail=True, methods=['get'], url_path='cotisations-total')
    def cotisations_total(self, request, pk=None):
        """Retourne le total des cotisations (montant cumulé) pour un membre donné."""
        try:
            membre = self.get_object()
            total = membre.total_cotisations() if hasattr(membre, 'total_cotisations') else 0
            return Response({
                'membre_id': membre.id,
                'total_cotisations': float(total)
            })
        except Exception:
            return Response({
                'membre_id': int(pk) if pk else None,
                'total_cotisations': 0
            })
    
    @action(detail=False, methods=['get'])
    def par_caisse(self, request):
        """Obtenir les membres groupés par caisse"""
        membres_par_caisse = Membre.objects.values('caisse__nom_association').annotate(
            total=Count('id'),
            actifs=Count('id', filter=Q(statut='ACTIF')),
            inactifs=Count('id', filter=Q(statut='INACTIF'))
        ).order_by('caisse__nom_association')
        
        return Response(membres_par_caisse)
    
    @action(detail=True, methods=['get'])
    def fiche_pdf(self, request, pk=None):
        """Télécharger le PDF de la fiche d'un membre"""
        membre = self.get_object()
        pdf = generate_membre_individual_pdf(membre)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=fiche_membre_{membre.nom_complet.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return response


class PretViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des prêts"""
    queryset = Pret.objects.select_related('membre', 'caisse').prefetch_related('echeances').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'caisse', 'membre']
    search_fields = ['numero_pret', 'membre__nom', 'membre__prenoms']
    ordering_fields = ['date_demande', 'montant_demande', 'statut']
    ordering = ['-date_demande']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PretListSerializer
        return PretSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses (membre ou agent)
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs
    
    def perform_create(self, serializer):
        try:
            # Déterminer la caisse cible avant de sauvegarder
            caisse = serializer.validated_data.get('caisse')
            caisse_id = serializer.validated_data.get('caisse_id')
            if not caisse and caisse_id:
                try:
                    caisse = Caisse.objects.get(pk=caisse_id)
                    serializer.validated_data['caisse'] = caisse
                except Caisse.DoesNotExist:
                    raise ValidationError({'caisse_id': "Caisse introuvable."})

            # Pour les non-admins, vérifier que la caisse appartient à l'utilisateur
            if not self.request.user.is_superuser:
                user_caisses = get_user_caisses(self.request.user)

                # Si c'est un membre (une seule caisse), utiliser automatiquement sa caisse
                if not AgentPermissions.is_agent(self.request.user):
                    caisse = get_user_caisse(self.request.user)
                    if not caisse:
                        raise ValidationError({'detail': 'Aucune caisse associée à votre compte.'})

                # Vérifier que la caisse sélectionnée appartient à l'utilisateur
                if caisse and caisse not in user_caisses:
                    raise ValidationError({'detail': 'Vous n\'avez pas accès à cette caisse.'})

            if not caisse:
                raise ValidationError({'caisse': "La caisse est obligatoire pour enregistrer un prêt."})

            # Vérifier l'existence d'un exercice en cours pour cette caisse
            ensure_caisse_has_active_exercice(caisse)

            # Valider le modèle avant la sauvegarde
            pret = serializer.save(caisse=caisse)
            pret.full_clean()

            # Ne pas calculer automatiquement le montant_accord ici
            # L'admin le définira lors de la validation
            
            # Si l'utilisateur n'est pas admin, soumettre pour validation
            if not self.request.user.is_superuser:
                pret.statut = 'EN_ATTENTE_ADMIN'
                pret.save()
                
                # Notifier la demande de prêt
                PretService.soumettre_demande_pret(pret, self.request.user)
            
            # Log de création
            AuditLog.objects.create(
                utilisateur=self.request.user,
                action='CREATION',
                modele='Pret',
                objet_id=pret.id,
                details={
                    'membre': pret.membre.nom_complet,
                    'montant_demande': str(pret.montant_demande),
                    'caisse': pret.caisse.nom_association,
                    'statut': pret.statut
                },
                ip_adresse=self.request.META.get('REMOTE_ADDR')
            )
        except ValidationError as e:
            # Re-raise les erreurs de validation avec le bon format
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else str(e))

    def perform_update(self, serializer):
        pret_instance = serializer.instance
        # Interdire la modification par un non-admin si le prêt est déjà validé ou plus avancé
        if not self.request.user.is_superuser and pret_instance.statut in ['VALIDE', 'EN_COURS', 'EN_RETARD', 'REMBOURSE', 'BLOQUE']:
            raise ValidationError({'detail': "Modification interdite: le prêt n'est plus en attente."})

        pret = serializer.save()
        # Log de modification
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='MODIFICATION',
            modele='Pret',
            objet_id=pret.id,
            details={'numero_pret': pret.numero_pret, 'membre': pret.membre.nom_complet},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
    
    @action(detail=False, methods=['get'])
    def check_member_loan(self, request):
        """Vérifier si un membre a un prêt en cours"""
        membre_id = request.query_params.get('membre_id')
        if not membre_id:
            return Response(
                {'error': 'Le paramètre membre_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import Pret
            prets_actifs = Pret.objects.filter(
                membre_id=membre_id,
                statut__in=['EN_ATTENTE', 'EN_ATTENTE_ADMIN', 'VALIDE', 'EN_COURS', 'EN_RETARD', 'BLOQUE']
            )
            
            has_active_loan = prets_actifs.exists()
            active_loan_info = None
            
            if has_active_loan:
                pret = prets_actifs.first()
                active_loan_info = {
                    'numero_pret': pret.numero_pret,
                    'statut': pret.statut,
                    'statut_display': pret.get_statut_display(),
                    'montant_demande': str(pret.montant_demande),
                    'date_demande': pret.date_demande.isoformat() if pret.date_demande else None
                }
            
            return Response({
                'has_active_loan': has_active_loan,
                'active_loan_info': active_loan_info
            })
            
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la vérification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valider un prêt (action réservée aux administrateurs)"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission refusée. Seuls les administrateurs peuvent valider les prêts.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        pret = self.get_object()
        if pret.statut != 'EN_ATTENTE_ADMIN':
            return Response(
                {'error': 'Ce prêt ne peut pas être validé. Il doit être en attente de validation admin.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pret = PretService.valider_pret(pret, request.user)
            serializer = self.get_serializer(pret)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la validation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        """Rejeter un prêt (action réservée aux administrateurs)"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission refusée. Seuls les administrateurs peuvent rejeter les prêts.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        pret = self.get_object()
        motif_rejet = request.data.get('motif_rejet', '')
        
        if not motif_rejet:
            return Response(
                {'error': 'Le motif de rejet est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if pret.statut != 'EN_ATTENTE_ADMIN':
            return Response(
                {'error': 'Ce prêt ne peut pas être rejeté. Il doit être en attente de validation admin.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pret = PretService.rejeter_pret(pret, request.user, motif_rejet)
            serializer = self.get_serializer(pret)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Erreur lors du rejet: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def en_retard(self, request):
        """Obtenir la liste des prêts en retard"""
        prets_en_retard = self.queryset.filter(statut='EN_COURS')
        # Logique pour identifier les prêts en retard
        # À implémenter selon la logique métier
        serializer = self.get_serializer(prets_en_retard, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mettre_en_attente(self, request, pk=None):
        """Mettre un prêt en attente (action réservée aux administrateurs)"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission refusée. Seuls les administrateurs peuvent mettre en attente les prêts.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        pret = self.get_object()
        motif_attente = request.data.get('motif_attente', '')
        
        if not motif_attente:
            return Response(
                {'error': 'Le motif de mise en attente est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if pret.statut != 'EN_ATTENTE_ADMIN':
            return Response(
                {'error': 'Ce prêt ne peut pas être mis en attente. Il doit être en attente de validation admin.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pret = PretService.mettre_en_attente_pret(pret, request.user, motif_attente)
            serializer = self.get_serializer(pret)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la mise en attente: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def octroyer(self, request, pk=None):
        """Octroyer un prêt validé au client"""
        pret = self.get_object()
        if pret.statut != 'VALIDE':
            return Response({'error': 'Seuls les prêts validés peuvent être octroyés.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pret = PretService.octroyer_pret(pret, request.user)
            serializer = self.get_serializer(pret)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': f"Erreur lors de l'octroi: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def rembourser(self, request, pk=None):
        """Enregistrer un remboursement (accès aux responsables de la caisse). Body: { montant, interet }"""
        pret = self.get_object()
        montant = request.data.get('montant')
        interet = request.data.get('interet', 0)
        try:
            montant = float(montant)
            interet = float(interet)
        except (TypeError, ValueError):
            return Response({'error': 'Montant (et intérêt) invalides'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pret, mouvement = PretService.rembourser_pret(pret, request.user, montant, interet)
            serializer = self.get_serializer(pret)
            data = serializer.data
            data.update({'mouvement_id': mouvement.id})
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def octroi_pdf(self, request, pk=None):
        """Télécharger le PDF d'octroi du prêt"""
        pret = self.get_object()
        # Le PDF est pertinent après octroi
        if pret.statut not in ['EN_COURS', 'REMBOURSE']:
            return Response({'error': "Le prêt n'est pas encore octroyé."}, status=status.HTTP_400_BAD_REQUEST)
        pdf = generate_pret_octroi_pdf(pret)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=octroi_{pret.numero_pret}.pdf"
        return response

    @action(detail=True, methods=['get'])
    def check_fonds(self, request, pk=None):
        """Vérifier les fonds disponibles pour un prêt"""
        pret = self.get_object()
        
        # Vérifier les permissions
        if not request.user.is_superuser:
            return Response({'error': 'Accès non autorisé'}, status=status.HTTP_403_FORBIDDEN)
        
        # Calculer le montant nécessaire
        montant_necessaire = pret.montant_accord or pret.montant_demande
        fonds_disponibles = pret.caisse.fond_disponible
        fonds_suffisants = fonds_disponibles >= montant_necessaire
        
        return Response({
            'pret_id': pret.id,
            'numero_pret': pret.numero_pret,
            'membre': {
                'id': pret.membre.id,
                'nom_complet': pret.membre.nom_complet
            },
            'caisse': {
                'id': pret.caisse.id,
                'nom_association': pret.caisse.nom_association,
                'fond_disponible': float(pret.caisse.fond_disponible)
            },
            'montant_demande': float(pret.montant_demande),
            'montant_accord': float(pret.montant_accord) if pret.montant_accord else None,
            'montant_necessaire': float(montant_necessaire),
            'fonds_disponibles': float(fonds_disponibles),
            'fonds_suffisants': fonds_suffisants,
            'difference': float(fonds_disponibles - montant_necessaire)
        })

    @action(detail=True, methods=['get'])
    def remboursement_pdf(self, request, pk=None):
        """Télécharger le reçu PDF de remboursement pour un mouvement donné"""
        pret = self.get_object()
        mouvement_id = request.query_params.get('mouvement_id')
        if not mouvement_id:
            return Response({'error': 'mouvement_id requis'}, status=status.HTTP_400_BAD_REQUEST)
        from .models import MouvementFond
        try:
            mouvement = MouvementFond.objects.get(id=mouvement_id, pret=pret, type_mouvement='REMBOURSEMENT')
        except MouvementFond.DoesNotExist:
            return Response({'error': 'Mouvement introuvable'}, status=status.HTTP_404_NOT_FOUND)
        pdf = generate_remboursement_pdf(pret, mouvement)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=remboursement_{pret.numero_pret}_{mouvement.id}.pdf"
        return response

    @action(detail=True, methods=['get'])
    def remboursement_complet_pdf(self, request, pk=None):
        """Télécharger le PDF complet de remboursement pour un prêt terminé"""
        pret = self.get_object()
        
        # Vérifier que le prêt est bien remboursé
        if pret.statut != 'REMBOURSE':
            return Response(
                {'error': 'Ce prêt n\'est pas encore entièrement remboursé'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer tous les mouvements de remboursement pour ce prêt
        from .models import MouvementFond
        mouvements_remboursement = MouvementFond.objects.filter(
            pret=pret, 
            type_mouvement='REMBOURSEMENT'
        ).order_by('date_mouvement')
        
        if not mouvements_remboursement.exists():
            return Response(
                {'error': 'Aucun mouvement de remboursement trouvé pour ce prêt'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Générer le PDF
        pdf = generate_remboursement_complet_pdf(pret, mouvements_remboursement)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=remboursement-complet_{pret.numero_pret}.pdf"
        return response

    @action(detail=True, methods=['delete'])
    def supprimer(self, request, pk=None):
        """Supprimer un prêt rejeté (action réservée aux administrateurs)"""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission refusée. Seuls les administrateurs peuvent supprimer les prêts.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pret = self.get_object()
        
        # Vérifier que le prêt est rejeté
        if pret.statut != 'REJETE':
            return Response(
                {'error': 'Seuls les prêts rejetés peuvent être supprimés.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Passer l'utilisateur courant au modèle pour le log d'audit
            pret._current_user = request.user
            
            # Supprimer le prêt (la logique est maintenant dans le modèle)
            pret.delete()
            
            return Response({'message': 'Prêt supprimé avec succès'})
            
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la suppression: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EcheanceViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des échéances"""
    queryset = Echeance.objects.select_related('pret').all()
    serializer_class = EcheanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'pret']
    search_fields = ['pret__numero_pret']
    ordering_fields = ['date_echeance', 'numero_echeance']
    ordering = ['pret', 'numero_echeance']
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(pret__caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs


class MouvementFondViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des mouvements de fonds"""
    queryset = MouvementFond.objects.select_related('caisse', 'pret', 'utilisateur').all()
    serializer_class = MouvementFondSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_mouvement', 'caisse']
    search_fields = ['description']
    ordering_fields = ['date_mouvement', 'montant']
    ordering = ['-date_mouvement']
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs





class VirementBancaireViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des virements bancaires"""
    queryset = VirementBancaire.objects.select_related('caisse').all()
    serializer_class = VirementBancaireSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['statut', 'caisse']
    search_fields = ['reference_bancaire', 'numero_compte_cible']
    ordering_fields = ['date_demande', 'montant']
    ordering = ['-date_demande']
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Restreindre les non-admins à leurs caisses
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                qs = qs.filter(caisse__in=user_caisses)
            else:
                qs = qs.none()
        return qs
    
    def perform_create(self, serializer):
        virement = serializer.save()
        # Log de création
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='CREATION',
            modele='VirementBancaire',
            objet_id=virement.id,
            details={
                'montant': str(virement.montant),
                'caisse': virement.caisse.nom_association
            },
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )


class CaisseGeneraleViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation de la Caisse Générale"""
    queryset = CaisseGenerale.objects.all()
    serializer_class = CaisseGeneraleSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='recalculer')
    def recalculer(self, request):
        cg = CaisseGenerale.get_instance()
        cg.recalculer_total_caisses()
        return Response(CaisseGeneraleSerializer(cg).data)


class CaisseGeneraleMouvementViewSet(viewsets.ModelViewSet):
    queryset = CaisseGeneraleMouvement.objects.select_related('caisse_destination', 'utilisateur').all()
    serializer_class = CaisseGeneraleMouvementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_mouvement', 'caisse_destination']
    search_fields = ['description']
    ordering_fields = ['date_mouvement', 'montant']
    ordering = ['-date_mouvement']


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la consultation des journaux d'audit (lecture seule)"""
    queryset = AuditLog.objects.select_related('utilisateur').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]  # Seuls les administrateurs peuvent consulter les logs
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['action', 'modele', 'utilisateur']
    search_fields = ['modele', 'details']
    ordering_fields = ['date_action', 'action']
    ordering = ['-date_action']


class DashboardViewSet(viewsets.ViewSet):
    """Vue pour le tableau de bord et les statistiques"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtenir les statistiques du tableau de bord (scopées aux caisses de l'utilisateur si non-admin)"""
        user_caisses = get_user_caisses(request.user)
        caisse_filter = {}
        if not request.user.is_superuser and user_caisses.exists():
            caisse_filter = {'caisse__in': user_caisses}
        
        # Statistiques
        if request.user.is_superuser:
            total_caisses = Caisse.objects.count()
        else:
            total_caisses = user_caisses.count() if user_caisses.exists() else 0
        
        total_membres = Membre.objects.filter(statut='ACTIF', **caisse_filter).count()
        # Considérer comme "actifs": tous les prêts non clôturés/annulés
        # Inclut: EN_ATTENTE, EN_ATTENTE_ADMIN, VALIDE, EN_COURS, EN_RETARD, BLOQUE
        statuts_actifs = ['EN_ATTENTE', 'EN_ATTENTE_ADMIN', 'VALIDE', 'EN_COURS', 'EN_RETARD', 'BLOQUE']
        total_prets_actifs = Pret.objects.filter(statut__in=statuts_actifs, **caisse_filter).count()
        
        # Montants financiers
        montant_total_circulation = Pret.objects.filter(statut='EN_COURS', **caisse_filter).aggregate(
            total=Sum('montant_accord')
        )['total'] or 0
        
        solde_total_disponible = user_caisses.aggregate(
            total=Sum('fond_disponible')
        )['total'] or 0 if user_caisses.exists() else Caisse.objects.all().aggregate(
            total=Sum('fond_disponible')
        )['total'] or 0
        
        # Répartition des caisses par région (admin uniquement), sinon vide
        caisses_par_region = [] if not request.user.is_superuser else list(Caisse.objects.values('region__nom').annotate(
            total=Count('id')
        ).order_by('region__nom'))
        
        # Évolution des prêts (6 derniers mois)
        evolution_prets = []
        for i in range(6):
            date = timezone.now() - timedelta(days=30*i)
            mois = date.strftime('%Y-%m')
            # Filtrer par caisse si l'utilisateur n'est pas admin
            pret_filter = {'date_demande__year': date.year, 'date_demande__month': date.month}
            if not request.user.is_superuser and user_caisses.exists():
                pret_filter['caisse__in'] = user_caisses
            count = Pret.objects.filter(**pret_filter).count()
            evolution_prets.append({'mois': mois, 'nombre': count})
        
        # Taux de remboursement (filtré par caisse)
        total_prets_accordes = Pret.objects.filter(statut__in=['EN_COURS', 'REMBOURSE'], **caisse_filter).count()
        total_prets_rembourses = Pret.objects.filter(statut='REMBOURSE', **caisse_filter).count()
        taux_remboursement = (total_prets_rembourses / total_prets_accordes * 100) if total_prets_accordes > 0 else 0
        
        # Notifications non lues pour l'utilisateur
        notifications_non_lues = Notification.objects.filter(
            destinataire=request.user,
            statut='NON_LU'
        ).count()
        
        # Demandes de prêt en attente (filtré par caisse pour les non-admins)
        demandes_pret_en_attente = Pret.objects.filter(statut='EN_ATTENTE_ADMIN', **caisse_filter).count()
        
        data = {
            'total_caisses': total_caisses,
            'total_membres': total_membres,
            'total_prets_actifs': total_prets_actifs,
            'montant_total_circulation': montant_total_circulation,
            'solde_total_disponible': solde_total_disponible,
            'caisses_par_region': caisses_par_region,
            'evolution_prets': evolution_prets,
            'taux_remboursement': round(taux_remboursement, 2),
            'notifications_non_lues': notifications_non_lues,
            'demandes_pret_en_attente': demandes_pret_en_attente
        }
        
        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='frais-fondation-total')
    def frais_fondation_total(self, request):
        """Somme totale des frais de fondation.
        
        - Admin: somme sur toutes les caisses
        - Non-admin: somme sur la caisse de l'utilisateur
        """
        from .models import Cotisation

        if request.user.is_superuser:
            agg = Cotisation.objects.aggregate(total_frais_fondation=Sum('frais_fondation'))
        else:
            user_caisses = get_user_caisses(request.user)
            if not user_caisses.exists():
                return Response({'total_frais_fondation': 0})
            agg = Cotisation.objects.filter(caisse__in=user_caisses).aggregate(total_frais_fondation=Sum('frais_fondation'))

        total = agg['total_frais_fondation'] or 0
        return Response({'total_frais_fondation': total})
    
    @action(detail=False, methods=['get'])
    def alertes(self, request):
        """Obtenir les alertes du système (scopées aux caisses de l'utilisateur si non-admin)"""
        user_caisses = get_user_caisses(request.user)
        caisse_filter = {}
        if not request.user.is_superuser and user_caisses.exists():
            caisse_filter = {'caisse__in': user_caisses}
        
        alertes = []
        
        # Prêts en retard (filtré par caisse)
        prets_en_retard = Pret.objects.filter(statut='EN_COURS', **caisse_filter)
        if prets_en_retard.exists():
            alertes.append({
                'type': 'PRETS_EN_RETARD',
                'message': f'{prets_en_retard.count()} prêts sont en retard',
                'niveau': 'warning'
            })
        
        # Caisses à fond insuffisant (filtré par caisse pour les non-admins)
        if request.user.is_superuser:
            caisses_fond_insuffisant = Caisse.objects.filter(fond_disponible__lt=10000)
        else:
            # Utiliser les caisses accessibles à l'utilisateur (agents, membres, etc.)
            if user_caisses.exists():
                caisses_fond_insuffisant = Caisse.objects.filter(id__in=user_caisses.values('id'), fond_disponible__lt=10000)
            else:
                caisses_fond_insuffisant = Caisse.objects.none()
        
        if caisses_fond_insuffisant.exists():
            alertes.append({
                'type': 'FOND_INSUFFISANT',
                'message': f'{caisses_fond_insuffisant.count()} caisses ont un fond insuffisant',
                'niveau': 'danger'
            })
        
        # Demandes en attente (filtré par caisse)
        demandes_en_attente = Pret.objects.filter(statut='EN_ATTENTE_ADMIN', **caisse_filter).count()
        if demandes_en_attente > 0:
            alertes.append({
                'type': 'DEMANDES_EN_ATTENTE',
                'message': f'{demandes_en_attente} demandes de prêt en attente de validation admin',
                'niveau': 'info'
            })
        
        return Response({'alertes': alertes})


class NotificationViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_notification', 'statut']
    search_fields = ['titre', 'message']
    ordering_fields = ['date_creation', 'statut']
    ordering = ['-date_creation']
    
    def get_queryset(self):
        """Retourner seulement les notifications de l'utilisateur connecté"""
        return Notification.objects.filter(destinataire=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NotificationListSerializer
        return NotificationSerializer
    
    @action(detail=True, methods=['post'])
    def marquer_comme_lu(self, request, pk=None):
        """Marquer une notification comme lue"""
        notification = self.get_object()
        notification.marquer_comme_lu()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def marquer_comme_traite(self, request, pk=None):
        """Marquer une notification comme traitée"""
        notification = self.get_object()
        notification.marquer_comme_traite()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def non_lues(self, request):
        """Obtenir le nombre de notifications non lues"""
        count = self.get_queryset().filter(statut='NON_LU').count()
        return Response({'count': count})
    
    @action(detail=False, methods=['get'])
    def demandes_pret_en_attente(self, request):
        """Obtenir uniquement les demandes de prêt en attente"""
        # Inclure les notifications liées aux prêts non validés, qu'elles soient lues ou non,
        # et couvrir les types DEMANDE_PRET (soumission) et ATTENTE_PRET (mise en attente)
        queryset = (
            self.get_queryset()
            .filter(type_notification__in=['DEMANDE_PRET', 'ATTENTE_PRET'])
            .select_related('pret')
            .order_by('-date_creation')
        )
        
        # Garder une seule notification par prêt, pour les statuts non validés
        # (EN_ATTENTE_ADMIN = en attente de validation admin, EN_ATTENTE = mis en attente)
        notifications_filtrees = []
        prets_vus = set()
        for notification in queryset:
            pret = notification.pret
            if not pret:
                continue
            if pret.id in prets_vus:
                continue
            if pret.statut in ['EN_ATTENTE_ADMIN', 'EN_ATTENTE']:
                notifications_filtrees.append(notification)
                prets_vus.add(pret.id)
        
        serializer = NotificationListSerializer(notifications_filtrees, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def count_demandes_pret_en_attente(self, request):
        """Obtenir le nombre de demandes de prêt en attente"""
        queryset = (
            self.get_queryset()
            .filter(type_notification__in=['DEMANDE_PRET', 'ATTENTE_PRET'])
            .select_related('pret')
            .order_by('-date_creation')
        )
        
        prets_vus = set()
        for notification in queryset:
            pret = notification.pret
            if not pret:
                continue
            if pret.id in prets_vus:
                continue
            if pret.statut in ['EN_ATTENTE_ADMIN', 'EN_ATTENTE']:
                prets_vus.add(pret.id)
        
        return Response({'count': len(prets_vus)})

    @action(detail=False, methods=['get'])
    def prets_en_attente_items(self, request):
        """Retourner des éléments "type notification" construits à partir des prêts en attente,
        indépendamment des notifications, pour alimenter la cloche.
        """
        # Réservé à l'admin dans l'interface d'administration
        if not request.user.is_superuser:
            return Response([], status=status.HTTP_200_OK)

        prets_qs = (
            Pret.objects
            .filter(statut__in=['EN_ATTENTE_ADMIN', 'EN_ATTENTE'])
            .select_related('membre', 'caisse')
            .order_by('-date_demande')
        )

        items = []
        for p in prets_qs:
            items.append({
                'id': p.id,
                'type_notification': 'DEMANDE_PRET',
                'titre': f"Demande de prêt - {p.membre.nom_complet}",
                'message': f"Montant: {p.montant_demande} FCFA • Caisse: {p.caisse.nom_association}",
                'caisse': getattr(p.caisse, 'nom_association', ''),
                'pret': str(p),
                'pret_id': p.id,
                'pret_statut': p.statut,
                'statut': 'NON_LU',
                'date_creation': p.date_demande,
                'lien_action': f"/adminsecurelogin/gestion_caisses/pret/{p.id}/change/",
            })

        return Response(items)

    @action(detail=False, methods=['get'])
    def count_prets_en_attente(self, request):
        """Compter les prêts en attente indépendamment des notifications."""
        if not request.user.is_superuser:
            return Response({'count': 0})

        count = Pret.objects.filter(statut__in=['EN_ATTENTE_ADMIN', 'EN_ATTENTE']).distinct().count()
        return Response({'count': count})


class UserManagementViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des utilisateurs par les administrateurs"""
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    
    def get_queryset(self):
        # Seuls les administrateurs peuvent voir tous les utilisateurs
        if not self.request.user.is_superuser:
            return User.objects.none()
        return User.objects.all()
    
    def perform_create(self, serializer):
        # Seuls les administrateurs peuvent créer des utilisateurs
        if not self.request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent créer des utilisateurs.'})
        
        user = serializer.save()
        
        # Log de création
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='CREATION',
            modele='User',
            objet_id=user.id,
            details={'username': user.username, 'email': user.email},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
    
    def perform_update(self, serializer):
        # Seuls les administrateurs peuvent modifier des utilisateurs
        if not self.request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent modifier des utilisateurs.'})
        
        user = serializer.save()
        
        # Log de modification
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='MODIFICATION',
            modele='User',
            objet_id=user.id,
            details={'username': user.username, 'email': user.email},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
    
    def perform_destroy(self, instance):
        # Seuls les administrateurs peuvent supprimer des utilisateurs
        if not self.request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent supprimer des utilisateurs.'})
        
        # Log de suppression
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='SUPPRESSION',
            modele='User',
            objet_id=instance.id,
            details={'username': instance.username, 'email': instance.email},
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )
        
        instance.delete()
    
    @action(detail=False, methods=['post'])
    def create_key_member(self, request):
        """Créer un utilisateur pour un membre clé (président, secrétaire, trésorier)"""
        if not request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent créer des membres clés.'})
        
        username = request.data.get('username')
        password = request.data.get('password')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        caisse_id = request.data.get('caisse_id')
        membre_id = request.data.get('membre_id')  # ID du membre existant
        
        if not all([username, password, first_name, last_name, caisse_id, membre_id]):
            raise ValidationError({'detail': 'Tous les champs sont requis.'})
        
        try:
            caisse = Caisse.objects.get(id=caisse_id)
        except Caisse.DoesNotExist:
            raise ValidationError({'detail': 'Caisse introuvable.'})
        
        try:
            membre = Membre.objects.get(id=membre_id, caisse=caisse)
        except Membre.DoesNotExist:
            raise ValidationError({'detail': 'Membre introuvable dans cette caisse.'})
        
        # Vérifier que le membre a un rôle clé
        if membre.role not in ['PRESIDENTE', 'SECRETAIRE', 'TRESORIERE']:
            raise ValidationError({'detail': 'Le membre sélectionné doit avoir un rôle clé (Présidente, Secrétaire, Trésorière).'})
        
        # Vérifier si le membre a déjà un compte utilisateur
        if membre.utilisateur:
            raise ValidationError({'detail': 'Ce membre a déjà un compte utilisateur.'})
        
        # Vérifier si l'utilisateur existe déjà
        if User.objects.filter(username=username).exists():
            raise ValidationError({'detail': 'Ce nom d\'utilisateur existe déjà.'})
        
        # Créer l'utilisateur
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            is_staff=False,
            is_superuser=False
        )
        
        # Lier l'utilisateur au membre existant
        membre.utilisateur = user
        membre.save()
        
        # Mettre à jour la caisse avec le membre clé
        if membre.role == 'PRESIDENTE':
            caisse.presidente = membre
        elif membre.role == 'SECRETAIRE':
            caisse.secretaire = membre
        elif membre.role == 'TRESORIERE':
            caisse.tresoriere = membre
        caisse.save()
        
        # Log de création
        AuditLog.objects.create(
            utilisateur=request.user,
            action='CREATION',
            modele='User',
            objet_id=user.id,
            details={
                'username': user.username,
                'role': membre.role,
                'caisse': caisse.nom_association,
                'membre_id': membre.id,
                'linked_to_existing': True
            },
            ip_adresse=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'success': True,
            'message': f'Utilisateur {membre.role.lower()} créé avec succès',
            'user': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'role': membre.role
            },
            'membre': {
                'id': membre.id,
                'numero_carte_electeur': membre.numero_carte_electeur,
                'nom_complet': membre.nom_complet
            }
        })

    @action(detail=False, methods=['get'])
    def key_members_by_caisse(self, request):
        """Récupérer les membres clés (président, secrétaire, trésorier) d'une caisse spécifique"""
        if not request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent accéder à cette information.'})
        
        caisse_id = request.query_params.get('caisse_id')
        if not caisse_id:
            raise ValidationError({'detail': 'L\'ID de la caisse est requis.'})
        
        try:
            caisse = Caisse.objects.get(id=caisse_id)
        except Caisse.DoesNotExist:
            raise ValidationError({'detail': 'Caisse introuvable.'})
        
        # Récupérer les membres clés de la caisse
        key_members = Membre.objects.filter(
            caisse=caisse,
            role__in=['PRESIDENTE', 'SECRETAIRE', 'TRESORIERE']
        ).select_related('utilisateur')
        
        members_data = []
        for membre in key_members:
            members_data.append({
                'id': membre.id,
                'nom_complet': f"{membre.prenoms} {membre.nom}",
                'role': membre.role,
                'numero_carte_electeur': membre.numero_carte_electeur,
                'has_user_account': membre.utilisateur is not None,
                'user_id': membre.utilisateur.id if membre.utilisateur else None
            })
        
        return Response({
            'success': True,
            'caisse': {
                'id': caisse.id,
                'nom': caisse.nom_association,
                'code': caisse.code
            },
            'key_members': members_data
        })




# ============================================================================
# FRONTEND ADMIN PERSONNALISÉ (rapports/états)
# ============================================================================

@login_required
def admin_frontend_view(request):
    """Interface frontend pour l'administrateur (rapports et états généraux)."""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    params = get_parametres_application()
    context = {
        'user': request.user,
        'user_role': 'Administrateur',
        'nom_application': params['nom_application'],
        'logo': params['logo'],
        'description_application': params['description_application'],
    }
    return render(request, 'gestion_caisses/admin_frontend.html', context)


@login_required
def rapports_global_api(request):
    """API JSON de rapports globaux (admin)."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)

    type_rapport = request.GET.get('type', 'general')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    try:
        date_debut_parsed = datetime.strptime(date_debut, '%Y-%m-%d').date() if date_debut else None
        date_fin_parsed = datetime.strptime(date_fin, '%Y-%m-%d').date() if date_fin else None
    except Exception:
        return JsonResponse({'error': 'Format de date invalide (YYYY-MM-DD).'}, status=400)

    if type_rapport == 'general':
        data = generer_rapport_general_global(date_debut_parsed, date_fin_parsed)
    elif type_rapport == 'financier':
        data = generer_rapport_financier_global(date_debut_parsed, date_fin_parsed)
    elif type_rapport == 'prets':
        data = generer_rapport_prets_global(date_debut_parsed, date_fin_parsed)
    elif type_rapport == 'membres':
        data = generer_rapport_membres_global(date_debut_parsed, date_fin_parsed)
    elif type_rapport == 'echeances':
        data = generer_rapport_echeances_global(date_debut_parsed, date_fin_parsed)
    else:
        return JsonResponse({'error': 'Type de rapport invalide'}, status=400)

    # Ajouter le bloc "Caisse Générale"
    try:
        data['caisse_generale'] = _build_caisse_generale_block(date_debut_parsed, date_fin_parsed)
    except Exception:
        data['caisse_generale'] = {'error': 'indisponible'}

    return JsonResponse(data)


@login_required
def admin_report_pdf(request):
    """Génère un PDF de rapport (global ou par caisse) pour l'admin."""
    if not request.user.is_superuser:
        return HttpResponse(status=403)

    type_rapport = request.GET.get('type', 'general')
    caisse_id = request.GET.get('caisse_id')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    try:
        date_debut_parsed = datetime.strptime(date_debut, '%Y-%m-%d').date() if date_debut else None
        date_fin_parsed = datetime.strptime(date_fin, '%Y-%m-%d').date() if date_fin else None
    except Exception:
        return HttpResponse('Format de date invalide (YYYY-MM-DD).', status=400)

    # Construire les données du rapport
    caisse = None
    if caisse_id:
        try:
            caisse = Caisse.objects.get(pk=caisse_id)
        except Caisse.DoesNotExist:
            return HttpResponse('Caisse introuvable', status=404)

    if caisse is None:
        # Rapports globaux
        if type_rapport == 'general':
            donnees = generer_rapport_general_global(date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'financier':
            donnees = generer_rapport_financier_global(date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'prets':
            donnees = generer_rapport_prets_global(date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'membres':
            donnees = generer_rapport_membres_global(date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'echeances':
            donnees = generer_rapport_echeances_global(date_debut_parsed, date_fin_parsed)
        else:
            return HttpResponse('Type de rapport invalide', status=400)
        # Bloc Caisse Générale
        try:
            donnees['caisse_generale'] = _build_caisse_generale_block(date_debut_parsed, date_fin_parsed)
        except Exception:
            donnees['caisse_generale'] = {'error': 'indisponible'}
    else:
        # Rapports par caisse
        if type_rapport == 'general':
            donnees = generer_rapport_general_caisse(caisse, date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'financier':
            donnees = generer_rapport_financier_caisse(caisse, date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'prets':
            donnees = generer_rapport_prets_caisse(caisse, date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'membres':
            donnees = generer_rapport_membres_caisse(caisse, date_debut_parsed, date_fin_parsed)
        elif type_rapport == 'echeances':
            donnees = generer_rapport_echeances_caisse(caisse, date_debut_parsed, date_fin_parsed)
        else:
            return HttpResponse('Type de rapport invalide', status=400)
        # Ajouter aussi le contexte Caisse Générale
        try:
            donnees['caisse_generale'] = _build_caisse_generale_block(date_debut_parsed, date_fin_parsed)
        except Exception:
            donnees['caisse_generale'] = {'error': 'indisponible'}

    # Créer un objet simple "virtuel" pour le moteur PDF
    rapport = SimpleNamespace(
        type_rapport=type_rapport,
        caisse=caisse,
        donnees=donnees,
        date_debut=date_debut_parsed,
        date_fin=date_fin_parsed,
    )

    try:
        from .utils import generate_rapport_pdf
        pdf_bytes = generate_rapport_pdf(rapport)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        label = caisse.code if caisse else 'GLOBAL'
        response['Content-Disposition'] = f"attachment; filename=rapport_{type_rapport}_{label}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return response
    except Exception as e:
        return HttpResponse(f'Erreur génération PDF: {e}', status=500)
@login_required
def agent_dashboard(request):
    """Tableau de bord personnalisé pour les agents"""
    
    # Vérifier si l'utilisateur est un agent
    if not AgentPermissions.is_agent(request.user):
        messages.error(request, "Accès non autorisé. Seuls les agents peuvent accéder à cette page.")
        return redirect('admin:index')
    
    agent = request.user.profil_agent
    caisses = AgentPermissions.get_agent_caisses(request.user)
    
    # Statistiques générales
    stats = {
        'total_caisses': caisses.count(),
        'caisses_actives': caisses.filter(statut='ACTIVE').count(),
        'caisses_inactives': caisses.filter(statut='INACTIVE').count(),
        'total_membres': Membre.objects.filter(caisse__in=caisses, statut='ACTIF').count(),
        'total_prets_actifs': Pret.objects.filter(caisse__in=caisses, statut='EN_COURS').count(),
        'total_fonds': caisses.aggregate(total=Sum('fond_disponible'))['total'] or 0,
        'total_prets_montant': caisses.aggregate(total=Sum('montant_total_prets'))['total'] or 0,
    }
    
    # Prêts récents
    prets_recents = Pret.objects.filter(caisse__in=caisses).order_by('-date_demande')[:10]
    
    # Mouvements récents
    mouvements_recents = MouvementFond.objects.filter(caisse__in=caisses).order_by('-date_mouvement')[:10]
    
    # Prêts en retard (à implémenter selon la logique métier)
    prets_en_retard = Pret.objects.filter(
        caisse__in=caisses,
        statut='EN_COURS'
    )[:5]  # Limiter à 5 pour l'exemple
    
    context = {
        'agent': agent,
        'caisses': caisses,
        'stats': stats,
        'prets_recents': prets_recents,
        'mouvements_recents': mouvements_recents,
        'prets_en_retard': prets_en_retard,
    }
    
    return render(request, 'adminsecurelogin/agent_dashboard.html', context)


@login_required
def agent_caisses_list(request):
    """Liste des caisses de l'agent"""
    
    if not AgentPermissions.is_agent(request.user):
        messages.error(request, "Accès non autorisé.")
        return redirect('admin:index')
    
    caisses = AgentPermissions.get_agent_caisses(request.user)
    
    # Statistiques par caisse
    for caisse in caisses:
        caisse.nombre_membres_actifs = caisse.membres.filter(statut='ACTIF').count()
        caisse.nombre_prets_actifs = caisse.prets.filter(statut='EN_COURS').count()
        caisse.solde_disponible = (caisse.fond_initial or 0) + (caisse.fond_disponible or 0)
    
    context = {
        'caisses': caisses,
        'agent': request.user.profil_agent,
    }
    
    return render(request, 'adminsecurelogin/agent_caisses_list.html', context)


@login_required
def agent_caisse_detail(request, caisse_id):
    """Détail d'une caisse pour l'agent"""
    
    if not AgentPermissions.is_agent(request.user):
        messages.error(request, "Accès non autorisé.")
        return redirect('admin:index')
    
    try:
        caisse = Caisse.objects.get(id=caisse_id)
        
        # Vérifier que l'agent a accès à cette caisse
        if not AgentPermissions.can_access_caisse(request.user, caisse):
            messages.error(request, "Vous n'avez pas accès à cette caisse.")
            return redirect('agent_caisses_list')
        
        # Statistiques de la caisse
        membres = caisse.membres.all()
        prets = caisse.prets.all()
        mouvements = caisse.mouvements_fonds.all().order_by('-date_mouvement')[:20]
        
        stats = {
            'total_membres': membres.count(),
            'membres_actifs': membres.filter(statut='ACTIF').count(),
            'total_prets': prets.count(),
            'prets_actifs': prets.filter(statut='EN_COURS').count(),
            'prets_rembourses': prets.filter(statut='REMBOURSE').count(),
            'fond_disponible': caisse.fond_disponible,
            'montant_total_prets': caisse.montant_total_prets,
            'solde_disponible': (caisse.fond_initial or 0) + (caisse.fond_disponible or 0),
        }
        
        context = {
            'caisse': caisse,
            'membres': membres,
            'prets': prets,
            'mouvements': mouvements,
            'stats': stats,
            'agent': request.user.profil_agent,
        }
        
        return render(request, 'adminsecurelogin/agent_caisse_detail.html', context)
        
    except Caisse.DoesNotExist:
        messages.error(request, "Caisse non trouvée.")
        return redirect('agent_caisses_list')


@login_required
def agent_stats_api(request):
    """API pour les statistiques en temps réel"""
    
    if not AgentPermissions.is_agent(request.user):
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)
    
    caisses = AgentPermissions.get_agent_caisses(request.user)
    
    # Statistiques en temps réel
    stats = {
        'total_caisses': caisses.count(),
        'caisses_actives': caisses.filter(statut='ACTIVE').count(),
        'total_membres': Membre.objects.filter(caisse__in=caisses, statut='ACTIF').count(),
        'total_prets_actifs': Pret.objects.filter(caisse__in=caisses, statut='EN_COURS').count(),
        'total_fonds': float(caisses.aggregate(total=Sum('fond_disponible'))['total'] or 0),
    }
    
    return JsonResponse(stats)

# ============================================================================
# VUES API POUR LES RAPPORTS DE CAISSE
# ============================================================================

@login_required
def caisses_cards_view(request):
    """Vue pour afficher toutes les caisses dans des cartes avec détails"""
    from django.db.models import Prefetch
    
    # Récupérer toutes les caisses avec leurs responsables et localisation
    caisses = Caisse.objects.select_related(
        'agent', 'village', 'canton', 'commune', 'prefecture', 'region',
        'presidente', 'secretaire', 'tresoriere'
    ).order_by('-date_creation')
    
        # Préparer les données pour chaque caisse
        caisses_data = []
        for caisse in caisses:
            # Récupérer l'exercice en cours (source unique de vérité: module Exercice de caisse)
            exercice_en_cours = (
                ExerciceCaisse.objects
                .filter(caisse=caisse, statut='EN_COURS')
                .order_by('-date_debut')
                .first()
            )
            exercice_actuel = serialize_exercice_info(exercice_en_cours)

        # Récupérer les 3 premiers responsables
        responsables = []
        if caisse.presidente:
            responsables.append({
                'nom': caisse.presidente.nom_complet,
                'role': 'Présidente',
                'telephone': caisse.presidente.numero_telephone
            })
        if caisse.secretaire:
            responsables.append({
                'nom': caisse.secretaire.nom_complet,
                'role': 'Secrétaire',
                'telephone': caisse.secretaire.numero_telephone
            })
        if caisse.tresoriere:
            responsables.append({
                'nom': caisse.tresoriere.nom_complet,
                'role': 'Trésorière',
                'telephone': caisse.tresoriere.numero_telephone
            })
        
        caisses_data.append({
            'caisse': caisse,
            'exercice_actuel': exercice_actuel,
            'responsables': responsables[:3],  # Limiter à 3
            'localisation': f"{caisse.village.nom}, {caisse.canton.nom}, {caisse.commune.nom}",
            'agent_responsable': caisse.agent.nom_complet if caisse.agent else 'Non assigné'
        })
    
    context = {
        'caisses_data': caisses_data,
        'total_caisses': len(caisses_data)
    }
    
    return render(request, 'gestion_caisses/caisses_cards.html', context)

@login_required
def rapports_caisse_api(request):
    """API pour les rapports de caisse"""
    try:
        # Si admin: rapports GLOBAUX (toutes caisses).
        # Si non admin (agents, membres, etc.) : rapports limités STRICTEMENT aux caisses auxquelles l'utilisateur a accès.
        caisse = None
        user = request.user
        is_admin = user.is_superuser
        multi_caisses_scope = False  # True si l'on agrège sur plusieurs caisses côté agent

        if not is_admin:
            caisse_id = request.GET.get('caisse_id')
            user_caisses_qs = get_user_caisses(user)

            if not user_caisses_qs.exists():
                return JsonResponse({'error': 'Aucune caisse associée'}, status=400)

            # Si un caisse_id explicite est demandé, vérifier qu'elle appartient bien aux caisses de l'utilisateur
            if caisse_id and caisse_id != '_ALL_MY_':
                if not user_caisses_qs.filter(id=caisse_id).exists():
                    return JsonResponse({'error': "Accès non autorisé à cette caisse"}, status=403)
                caisse = user_caisses_qs.get(id=caisse_id)
                multi_caisses_scope = False  # Rapport mono-caisse
            else:
                # Pas de caisse_id explicite ou "_ALL_MY_" : on considère un scope multi-caisses
                multi_caisses_scope = True
                caisse = None  # Pas de caisse unique, on veut toutes les caisses
        
        # Paramètres de filtrage
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        type_rapport = request.GET.get('type', 'general')
        
        # Convertir les dates
        if date_debut:
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
        if date_fin:
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
        
        # Générer le rapport selon le type
        # - Admin : global (toutes les caisses)
        # - Non admin : si une caisse précise est fournie => rapport de cette caisse
        #               sinon => rapport agrégé sur toutes ses caisses
        if type_rapport in ['general', 'financier', 'prets', 'membres', 'echeances'] and not is_admin:
            # Pour les non-admins, déterminer si on fait un rapport mono-caisse ou multi-caisses
            user_caisses_qs = get_user_caisses(user)
            if caisse is not None and not multi_caisses_scope:
                # Rapport pour une seule caisse (caisse_id explicite fourni)
                if type_rapport == 'general':
                    rapport = generer_rapport_general_caisse(caisse, date_debut, date_fin)
                elif type_rapport == 'financier':
                    rapport = generer_rapport_financier_caisse(caisse, date_debut, date_fin)
                elif type_rapport == 'prets':
                    rapport = generer_rapport_prets_caisse(caisse, date_debut, date_fin)
                elif type_rapport == 'membres':
                    rapport = generer_rapport_membres_caisse(caisse, date_debut, date_fin)
                else:  # echeances
                    rapport = generer_rapport_echeances_caisse(caisse, date_debut, date_fin)
            else:
                # Rapport agrégé sur toutes les caisses de l'utilisateur (agent)
                # (caisse = None ou multi_caisses_scope = True)
                if type_rapport == 'general':
                    rapport = generer_rapport_general_global(date_debut, date_fin, caisses_qs=user_caisses_qs)
                elif type_rapport == 'financier':
                    rapport = generer_rapport_financier_global(date_debut, date_fin, caisses_qs=user_caisses_qs)
                elif type_rapport == 'prets':
                    rapport = generer_rapport_prets_global(date_debut, date_fin, caisses_qs=user_caisses_qs)
                elif type_rapport == 'membres':
                    rapport = generer_rapport_membres_global(date_debut, date_fin, caisses_qs=user_caisses_qs)
                else:  # echeances
                    rapport = generer_rapport_echeances_global(date_debut, date_fin, caisses_qs=user_caisses_qs)
        else:
            # Cas admin : toujours global toutes caisses
            if type_rapport == 'general':
                rapport = generer_rapport_general_global(date_debut, date_fin)
            elif type_rapport == 'financier':
                rapport = generer_rapport_financier_global(date_debut, date_fin)
            elif type_rapport == 'prets':
                rapport = generer_rapport_prets_global(date_debut, date_fin)
            elif type_rapport == 'membres':
                rapport = generer_rapport_membres_global(date_debut, date_fin)
            elif type_rapport == 'echeances':
                rapport = generer_rapport_echeances_global(date_debut, date_fin)

        if type_rapport == 'cotisations_general':
            # Rapport des cotisations (liste)
            # Admin sans caisse_id => global; Agent sans caisse_id => toutes ses caisses; sinon filtré par caisse
            if (is_admin and caisse is None) or (not is_admin and caisse is None):
                if is_admin:
                    cotisations = Cotisation.objects.all()
                    caisse_info = {'code': 'GLOBAL', 'nom': 'Toutes les caisses'}
                else:
                    # Agent : toutes ses caisses
                    user_caisses_qs = get_user_caisses(user)
                    cotisations = Cotisation.objects.filter(caisse__in=user_caisses_qs)
                    caisse_info = {'code': 'MES_CAISSES', 'nom': 'Toutes mes caisses'}
            else:
                cotisations = Cotisation.objects.filter(caisse=caisse)
                caisse_info = {'code': caisse.code, 'nom': caisse.nom_association}
            if date_debut:
                cotisations = cotisations.filter(date_cotisation__date__gte=date_debut)
            if date_fin:
                cotisations = cotisations.filter(date_cotisation__date__lte=date_fin)
            items = [
                {
                    'date_cotisation': c.date_cotisation.strftime('%d/%m/%Y %H:%M'),
                    'membre': c.membre.nom_complet,
                    'seance': c.seance.date_seance.strftime('%d/%m/%Y'),
                    'prix_tempon': float(c.prix_tempon or 0),
                    'frais_solidarite': float(c.frais_solidarite or 0),
                    'frais_fondation': float(c.frais_fondation or 0),
                    'penalite_emprunt_retard': float(c.penalite_emprunt_retard or 0),
                    'montant_total': float(c.montant_total or 0),
                    'observation': c.description or '',
                }
                for c in cotisations.order_by('-date_cotisation')
            ]
            rapport = {
                'type': 'cotisations_general',
                'caisse': caisse_info,
                'periode': {'debut': date_debut.strftime('%d/%m/%Y') if date_debut else '', 'fin': date_fin.strftime('%d/%m/%Y') if date_fin else ''},
                'items': items,
                'totaux': {
                    'tempon': sum(i['prix_tempon'] for i in items),
                    'solidarite': sum(i['frais_solidarite'] for i in items),
                    'fondation': sum(i['frais_fondation'] for i in items),
                    'penalite': sum(i['penalite_emprunt_retard'] for i in items),
                    'total': sum(i['montant_total'] for i in items),
                    'nombre': len(items),
                }
            }
        elif type_rapport == 'cotisations_par_membre':
            from collections import defaultdict
            # Admin sans caisse_id => global; Agent sans caisse_id => toutes ses caisses; sinon filtré par caisse
            if (is_admin and caisse is None) or (not is_admin and caisse is None):
                if is_admin:
                    cotisations = Cotisation.objects.all()
                    caisse_info = {'code': 'GLOBAL', 'nom': 'Toutes les caisses'}
                else:
                    # Agent : toutes ses caisses
                    user_caisses_qs = get_user_caisses(user)
                    cotisations = Cotisation.objects.filter(caisse__in=user_caisses_qs)
                    caisse_info = {'code': 'MES_CAISSES', 'nom': 'Toutes mes caisses'}
            else:
                cotisations = Cotisation.objects.filter(caisse=caisse)
                caisse_info = {'code': caisse.code, 'nom': caisse.nom_association}
            if date_debut:
                cotisations = cotisations.filter(date_cotisation__date__gte=date_debut)
            if date_fin:
                cotisations = cotisations.filter(date_cotisation__date__lte=date_fin)
            agg = defaultdict(lambda: {'nom': '', 'tempon':0.0, 'solidarite':0.0, 'fondation':0.0, 'penalite':0.0, 'total':0.0, 'nombre':0})
            for c in cotisations.select_related('membre'):
                a = agg[c.membre_id]
                a['nom'] = c.membre.nom_complet
                a['tempon'] += float(c.prix_tempon or 0)
                a['solidarite'] += float(c.frais_solidarite or 0)
                a['fondation'] += float(c.frais_fondation or 0)
                a['penalite'] += float(c.penalite_emprunt_retard or 0)
                a['total'] += float(c.montant_total or 0)
                a['nombre'] += 1
            items = [{'membre': v['nom'], **{k:v[k] for k in ['tempon','solidarite','fondation','penalite','total','nombre']}} for v in agg.values()]
            rapport = {
                'type': 'cotisations_par_membre',
                'caisse': caisse_info,
                'periode': {'debut': date_debut.strftime('%d/%m/%Y') if date_debut else '', 'fin': date_fin.strftime('%d/%m/%Y') if date_fin else ''},
                'items': items,
                'totaux': {
                    'tempon': sum(i['tempon'] for i in items),
                    'solidarite': sum(i['solidarite'] for i in items),
                    'fondation': sum(i['fondation'] for i in items),
                    'penalite': sum(i['penalite'] for i in items),
                    'total': sum(i['total'] for i in items),
                    'nombre': sum(i['nombre'] for i in items),
                }
            }
        elif type_rapport == 'depenses':
            # Pour les admins: permettre de filtrer par caisse_id ou afficher toutes les dépenses
            if is_admin:
                caisse_id_param = request.GET.get('caisse_id')
                if caisse_id_param:
                    try:
                        caisse = Caisse.objects.get(id=caisse_id_param)
                        depenses = Depense.objects.filter(caisse=caisse)
                        caisse_info = caisse
                    except Caisse.DoesNotExist:
                        return JsonResponse({'error': 'Caisse introuvable'}, status=404)
                else:
                    # Admin sans caisse_id => toutes les dépenses
                    depenses = Depense.objects.all()
                    caisse_info = None
            else:
                # Non-admin: filtrer par sa caisse ou toutes ses caisses selon le contexte
                if caisse is None:
                    # Agent veut toutes ses caisses
                    user_caisses_qs = get_user_caisses(user)
                    depenses = Depense.objects.filter(caisse__in=user_caisses_qs)
                    caisse_info = None
                else:
                    # Agent veut une caisse spécifique
                    depenses = Depense.objects.filter(caisse=caisse)
                    caisse_info = caisse
            
            if date_debut:
                depenses = depenses.filter(datedepense__gte=date_debut)
            if date_fin:
                depenses = depenses.filter(datedepense__lte=date_fin)
            
            items = [
                {
                    'date': d.datedepense.strftime('%d/%m/%Y') if d.datedepense else '',
                    'objectif': d.Objectifdepense or '',
                    'montant': float(d.montantdepense or 0),
                    'observation': d.observation or '',
                    'caisse_nom': d.caisse.nom_association if d.caisse else ''  # Ajouter le nom de la caisse pour les admins
                }
                for d in depenses.select_related('caisse').order_by('-datedepense', '-date_creation')
            ]
            rapport = {
                'type': 'depenses',
                'caisse': caisse_info,  # Passer l'objet caisse complet pour le PDF (None si toutes les caisses)
                'periode': {'debut': date_debut.strftime('%d/%m/%Y') if date_debut else '', 'fin': date_fin.strftime('%d/%m/%Y') if date_fin else ''},
                'items': items,
                'totaux': {
                    'montant': sum(i['montant'] for i in items),
                    'nombre': len(items)
                }
            }
        elif type_rapport == 'cotisations_membre':
            # Rapport des cotisations d'un seul membre (demandé)
            # - Pour les agents : limité à leur(s) caisse(s) (variable `caisse` déjà positionnée plus haut)
            # - Pour les administrateurs : autoriser n'importe quel membre du système
            membre_id = request.GET.get('membre') or request.GET.get('membre_id')
            if not membre_id:
                return JsonResponse({'error': 'Paramètre membre (ou membre_id) requis'}, status=400)

            try:
                if is_admin:
                    # L'admin peut générer un rapport pour n'importe quel membre ;
                    # la caisse du membre devient alors la caisse de référence du rapport.
                    membre = Membre.objects.select_related('caisse').get(pk=membre_id)
                    caisse = membre.caisse
                else:
                    # Pour les non-admins, on reste strictement dans le périmètre de leurs caisses
                    membre = Membre.objects.get(pk=membre_id, caisse=caisse)
            except Membre.DoesNotExist:
                return JsonResponse({'error': 'Membre introuvable dans cette caisse'}, status=404)

            cotisations = Cotisation.objects.filter(caisse=caisse, membre=membre)
            if date_debut:
                cotisations = cotisations.filter(date_cotisation__date__gte=date_debut)
            if date_fin:
                cotisations = cotisations.filter(date_cotisation__date__lte=date_fin)
            items = [
                {
                    'seance': c.seance.date_seance.strftime('%d/%m/%Y'),
                    'prix_tempon': float(c.prix_tempon or 0),
                    'frais_solidarite': float(c.frais_solidarite or 0),
                    'penalite_emprunt_retard': float(c.penalite_emprunt_retard or 0),
                    'montant_total': float(c.montant_total or 0),
                    'observation': c.description or '',
                }
                for c in cotisations.order_by('-date_cotisation')
            ]
            rapport = {
                'type': 'cotisations_membre',
                'caisse': {'code': caisse.code, 'nom': caisse.nom_association},
                'membre': {'id': membre.id, 'nom': membre.nom_complet},
                'periode': {'debut': date_debut.strftime('%d/%m/%Y') if date_debut else '', 'fin': date_fin.strftime('%d/%m/%Y') if date_fin else ''},
                'items': items,
                'totaux': {
                    'tempon': sum(i['prix_tempon'] for i in items),
                    'solidarite': sum(i['frais_solidarite'] for i in items),
                    'penalite': sum(i['penalite_emprunt_retard'] for i in items),
                    'total': sum(i['montant_total'] for i in items),
                    'nombre': len(items),
                }
            }
        elif type_rapport in ['membres_systeme_pdf', 'agents_systeme_pdf', 'prets_evaluation_pdf', 'prets_par_motif']:
            # Ces types renvoient directement un PDF global
            from .utils import generate_membres_systeme_pdf, generate_agents_systeme_pdf, generate_prets_evaluation_pdf, generate_prets_par_motif_pdf
            if type_rapport == 'membres_systeme_pdf':
                pdf_bytes = generate_membres_systeme_pdf()
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f"attachment; filename=membres_systeme_{datetime.now().strftime('%Y-%m-%d')}.pdf"
                return response
            elif type_rapport == 'agents_systeme_pdf':
                pdf_bytes = generate_agents_systeme_pdf()
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f"attachment; filename=agents_systeme_{datetime.now().strftime('%Y-%m-%d')}.pdf"
                return response
            elif type_rapport == 'prets_evaluation_pdf':
                # Période & caisse optionnels (réutiliser les dates déjà parsées plus haut)
                caisse_id = request.GET.get('caisse_id')
                pdf_bytes = generate_prets_evaluation_pdf(date_debut, date_fin, caisse_id)
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f"attachment; filename=prets_evaluation_{datetime.now().strftime('%Y-%m-%d')}.pdf"
                return response
            else:
                # Préts par motif (ADMIN global uniquement)
                if not request.user.is_superuser:
                    return JsonResponse({'error': 'Réservé aux administrateurs'}, status=403)
                motif = request.GET.get('motif')
                output_format = request.GET.get('format')
                # JSON ou PDF
                if output_format == 'pdf':
                    pdf_bytes = generate_prets_par_motif_pdf(motif, date_debut, date_fin)
                    response = HttpResponse(pdf_bytes, content_type='application/pdf')
                    response['Content-Disposition'] = f"attachment; filename=prets_par_motif_{motif or 'tous'}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
                    return response
                else:
                    # JSON de synthèse
                    from django.db.models import Q
                    qs = Pret.objects.select_related('membre','caisse')
                    if motif:
                        qs = qs.filter(Q(motif__iexact=motif) | Q(motif__icontains=motif))
                    if date_debut:
                        qs = qs.filter(date_demande__date__gte=date_debut)
                    if date_fin:
                        qs = qs.filter(date_demande__date__lte=date_fin)
                    items = []
                    for p in qs:
                        # calcul % remboursé
                        total = getattr(p, 'total_a_rembourser', 0) or 0
                        restant = getattr(p, 'montant_restant', 0) or 0
                        pct = 0
                        if total > 0:
                            pct = round((total - max(0, restant)) / total * 100)
                            if pct < 0: pct = 0
                            if pct > 100: pct = 100
                        items.append({
                            'numero_pret': p.numero_pret,
                            'membre': getattr(p.membre, 'nom_complet', ''),
                            'caisse': getattr(p.caisse, 'nom_association', ''),
                            'pourcentage': pct,
                        })
                    return JsonResponse({
                        'motif': motif or 'Tous',
                        'nombre': len(items),
                        'items': items,
                        'totaux': {},
                    })
        else:
            # Ne considérer comme invalide que les types qui ne sont pas déjà gérés plus haut
            if type_rapport not in ['general', 'financier', 'prets', 'membres', 'echeances']:
                return JsonResponse({'error': 'Type de rapport invalide'}, status=400)
        
        # Si on demande un PDF, retourner un binaire PDF
        output_format = request.GET.get('format')
        if output_format == 'pdf':
            from types import SimpleNamespace
            from .utils import generate_rapport_pdf

            # Pour les agents en mode "toutes mes caisses", on ne doit pas afficher une caisse unique dans l'en-tête
            caisse_for_pdf = None if (is_admin or multi_caisses_scope) else caisse

            rapobj = SimpleNamespace(
                type_rapport=type_rapport,
                caisse=caisse_for_pdf,
                date_debut=date_debut,
                date_fin=date_fin,
                donnees=rapport,
            )
            pdf_bytes = generate_rapport_pdf(rapobj)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            if is_admin:
                label = 'toutes_caisses'
            elif multi_caisses_scope:
                label = 'mes_caisses'
            else:
                label = caisse.code if caisse else 'caisse'
            response['Content-Disposition'] = f"attachment; filename=rapport_{type_rapport}_{label}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
            return response

        # Sinon JSON enrichi
        try:
            rapport['caisse_generale'] = _build_caisse_generale_block(date_debut, date_fin)
        except Exception:
            rapport['caisse_generale'] = {'error': 'indisponible'}
        return JsonResponse(rapport)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def generer_rapport_general_caisse(caisse, date_debut=None, date_fin=None):
    """Génère un rapport général de la caisse"""
    from django.db.models import Count, Sum, Avg, Q
    from django.utils import timezone
    
    # Filtres de date pour chaque type de données
    filtres_date_membres = Q()
    filtres_date_prets = Q()
    filtres_date_mouvements = Q()
    
    if date_debut:
        filtres_date_membres &= Q(date_creation__gte=date_debut)
        filtres_date_prets &= Q(date_demande__gte=date_debut)
        filtres_date_mouvements &= Q(date_mouvement__gte=date_debut)
    if date_fin:
        filtres_date_membres &= Q(date_creation__lte=date_fin)
        filtres_date_prets &= Q(date_demande__lte=date_fin)
        filtres_date_mouvements &= Q(date_mouvement__lte=date_fin)
    
    # Statistiques des membres (avec filtre de date)
    membres_stats = caisse.membres.filter(filtres_date_membres).aggregate(
        total=Count('id'),
        actifs=Count('id', filter=Q(statut='ACTIF')),
        inactifs=Count('id', filter=Q(statut='INACTIF')),
        suspendus=Count('id', filter=Q(statut='SUSPENDU')),
        femmes=Count('id', filter=Q(sexe='F')),
        hommes=Count('id', filter=Q(sexe='M'))
    )
    
    # Statistiques des prêts (avec filtre de date)
    prets_stats = caisse.prets.filter(filtres_date_prets).aggregate(
        total=Count('id'),
        en_cours=Count('id', filter=Q(statut='EN_COURS')),
        rembourses=Count('id', filter=Q(statut='REMBOURSE')),
        en_retard=Count('id', filter=Q(statut='EN_RETARD')),
        montant_total=Sum('montant_accord'),
        montant_rembourse=Sum('montant_rembourse'),
        montant_moyen=Avg('montant_accord')
    )
    
    # Mouvements de fonds (avec filtre de date)
    mouvements = caisse.mouvements_fonds.filter(filtres_date_mouvements).aggregate(
        total_alimentations=Sum('montant', filter=Q(type_mouvement='ALIMENTATION')),
        total_decaissements=Sum('montant', filter=Q(type_mouvement='DECAISSEMENT')),
        total_remboursements=Sum('montant', filter=Q(type_mouvement='REMBOURSEMENT')),
        total_frais=Sum('montant', filter=Q(type_mouvement='FRAIS'))
    )
    
    # Échéances en retard
    echeances_retard = caisse.prets.filter(statut__in=['EN_COURS', 'EN_RETARD']).aggregate(
        total_echeances_retard=Sum('echeances__id', filter=Q(echeances__statut='EN_RETARD')),
        montant_retard=Sum('echeances__montant_echeance', filter=Q(echeances__statut='EN_RETARD'))
    )
    
    return {
        'caisse': {
            'nom': caisse.nom_association,
            'code': caisse.code,
            'date_creation': caisse.date_creation.strftime('%d/%m/%Y'),
            'statut': caisse.statut,
        },
        'membres': membres_stats,
        'prets': prets_stats,
        'mouvements': mouvements,
        'echeances_retard': echeances_retard,
        'fonds': {
            'fond_initial': float(caisse.fond_initial),
            'fond_disponible': float(caisse.fond_disponible),
            'montant_total_prets': float(caisse.montant_total_prets),
            'solde_disponible': float(caisse.solde_disponible),
        },
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }


def generer_rapport_general_global(date_debut=None, date_fin=None, caisses_qs=None):
    """Rapport général agrégé pour un ensemble de caisses (toutes par défaut),
    même structure que le frontend.

    - Si `caisses_qs` est None: toutes les caisses.
    - Sinon: uniquement les caisses de ce queryset (utile pour les agents).
    """
    from django.db.models import Count, Sum, Avg, Q
    caisses = caisses_qs if caisses_qs is not None else Caisse.objects.all()
    
    # Filtres de date pour chaque type de données
    filtres_date_membres = Q()
    filtres_date_prets = Q()
    filtres_date_mouvements = Q()
    
    if date_debut:
        filtres_date_membres &= Q(date_creation__gte=date_debut)
        filtres_date_prets &= Q(date_demande__gte=date_debut)
        filtres_date_mouvements &= Q(date_mouvement__gte=date_debut)
    if date_fin:
        filtres_date_membres &= Q(date_creation__lte=date_fin)
        filtres_date_prets &= Q(date_demande__lte=date_fin)
        filtres_date_mouvements &= Q(date_mouvement__lte=date_fin)
    
    # Appliquer les filtres de date (limités aux caisses sélectionnées)
    membres = Membre.objects.filter(caisse__in=caisses).filter(filtres_date_membres)
    prets = Pret.objects.filter(caisse__in=caisses).filter(filtres_date_prets)
    mouvements = MouvementFond.objects.filter(caisse__in=caisses).filter(filtres_date_mouvements)

    membres_stats = {
        'total': membres.count(),
        'actifs': membres.filter(statut='ACTIF').count(),
        'inactifs': membres.filter(statut='INACTIF').count(),
        'suspendus': membres.filter(statut='SUSPENDU').count(),
        'femmes': membres.filter(sexe='F').count(),
        'hommes': membres.filter(sexe='M').count(),
    }

    # Montants robustes basés sur les prêts accordés (en cours + remboursés)
    prets_accordes = prets.filter(statut__in=['EN_COURS', 'REMBOURSE', 'EN_RETARD'])
    total_prets_accordes = prets_accordes.aggregate(total=Sum('montant_accord'))['total'] or 0
    total_rembourse = prets.aggregate(total=Sum('montant_rembourse'))['total'] or 0
    # Reste à rembourser (sur prêts non soldés)
    from django.db.models import F, ExpressionWrapper, DecimalField
    restant_qs = prets.filter(statut__in=['EN_COURS', 'EN_RETARD']).annotate(
        restant=ExpressionWrapper((F('montant_accord') - F('montant_rembourse')), output_field=DecimalField(max_digits=15, decimal_places=2))
    )
    total_restant = restant_qs.aggregate(total=Sum('restant'))['total'] or 0

    prets_stats = {
        'total': prets.count(),
        'en_cours': prets.filter(statut='EN_COURS').count(),
        'rembourses': prets.filter(statut='REMBOURSE').count(),
        'en_retard': prets.filter(statut='EN_RETARD').count(),
        'montant_total': float(total_prets_accordes),
        'montant_rembourse': float(total_rembourse),
        'montant_restant': float(total_restant),
        'montant_moyen': float(prets.aggregate(moy=Avg('montant_accord'))['moy'] or 0),
    }

    mouvements_aggr = mouvements.aggregate(
        total_alimentations=Sum('montant', filter=Q(type_mouvement='ALIMENTATION')),
        total_decaissements=Sum('montant', filter=Q(type_mouvement='DECAISSEMENT')),
        total_remboursements=Sum('montant', filter=Q(type_mouvement='REMBOURSEMENT')),
        total_frais=Sum('montant', filter=Q(type_mouvement='FRAIS'))
    )

    total_fond_initial = caisses.aggregate(total=Sum('fond_initial'))['total'] or 0
    total_fond_disponible = caisses.aggregate(total=Sum('fond_disponible'))['total'] or 0
    fonds = {
        'fond_initial': float(total_fond_initial),
        'fond_disponible': float(total_fond_disponible),
        'montant_total_prets': float(total_prets_accordes),
        'solde_disponible': float((total_fond_initial or 0) + (total_fond_disponible or 0)),
    }

    echeances_retard = {
        'total_echeances_retard': Echeance.objects.filter(pret__caisse__in=caisses, statut='EN_RETARD').count(),
        'montant_retard': float(Echeance.objects.filter(pret__caisse__in=caisses, statut='EN_RETARD').aggregate(total=Sum('montant_echeance'))['total'] or 0),
    }

    # Détail par caisse pour les rapports PDF : chaque caisse de l'agent (ou du système)
    # avec quelques indicateurs clés
    from django.db.models import Count as DJCount
    membres_par_caisse = {
        row['caisse_id']: row['nb']
        for row in membres.values('caisse_id').annotate(nb=DJCount('id'))
    }
    prets_par_caisse = {
        row['caisse_id']: {
            'nb_prets': row['nb'],
            'montant_total_prets': float(row['montant'] or 0),
        }
        for row in prets.values('caisse_id').annotate(
            nb=DJCount('id'),
            montant=Sum('montant_accord'),
        )
    }
    caisses_details = []
    for c in caisses:
        stats_pret = prets_par_caisse.get(c.id, {})
        caisses_details.append({
            'code': c.code,
            'nom': c.nom_association,
            'statut': c.statut,
            'fond_initial': float(c.fond_initial or 0),
            'fond_disponible': float(c.fond_disponible or 0),
            'nb_membres': membres_par_caisse.get(c.id, 0),
            'nb_prets': stats_pret.get('nb_prets', 0),
            'montant_total_prets': stats_pret.get('montant_total_prets', 0.0),
        })

    return {
        'caisse': {
            'nom': 'Toutes les caisses',
            'code': 'GLOBAL',
            'date_creation': None,
            'statut': 'AGREGE',
        },
        'caisses_details': caisses_details,
        'membres': membres_stats,
        'prets': prets_stats,
        'mouvements': mouvements_aggr,
        'echeances_retard': echeances_retard,
        'fonds': fonds,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }

def generer_rapport_financier_caisse(caisse, date_debut=None, date_fin=None):
    """Génère un rapport financier détaillé de la caisse"""
    from django.db.models import Sum, Q
    from django.utils import timezone
    
    # Filtres de date (timezone-aware)
    from django.utils import timezone
    start_dt = end_dt = None
    if date_debut:
        start_dt = timezone.make_aware(datetime.combine(date_debut, time.min), timezone.get_current_timezone())
    if date_fin:
        end_dt = timezone.make_aware(datetime.combine(date_fin, time.max), timezone.get_current_timezone())
    filtres_date = Q()
    if start_dt:
        filtres_date &= Q(date_mouvement__gte=start_dt)
    if end_dt:
        filtres_date &= Q(date_mouvement__lte=end_dt)
    
    # Mouvements de fonds détaillés
    mouvements = caisse.mouvements_fonds.filter(filtres_date).order_by('-date_mouvement')
    
    # Statistiques par type de mouvement
    stats_mouvements = mouvements.values('type_mouvement').annotate(
        total=Sum('montant'),
        nombre=Count('id')
    )
    
    # Évolution des fonds
    evolution_fonds = []
    fond_courant = float(caisse.fond_initial)
    
    for mouvement in mouvements.order_by('date_mouvement'):
        if mouvement.type_mouvement == 'ALIMENTATION':
            fond_courant += float(mouvement.montant)
        elif mouvement.type_mouvement == 'DECAISSEMENT':
            fond_courant -= float(mouvement.montant)
        elif mouvement.type_mouvement == 'REMBOURSEMENT':
            fond_courant += float(mouvement.montant)
        elif mouvement.type_mouvement == 'FRAIS':
            fond_courant -= float(mouvement.montant)
        
        evolution_fonds.append({
            'date': mouvement.date_mouvement.strftime('%d/%m/%Y'),
            'type': mouvement.type_mouvement,
            'montant': float(mouvement.montant),
            'solde': fond_courant,
            'description': mouvement.description
        })
    
    # Synthèse des prêts par statut et montants
    from django.db.models import F, ExpressionWrapper, DecimalField
    prets_caisse = caisse.prets.all()
    total_prets_caisse = prets_caisse.filter(statut__in=['EN_COURS','REMBOURSE','EN_RETARD'])\
        .aggregate(total=Sum('montant_accord'))['total'] or 0
    total_prets_octroyes = prets_caisse.filter(statut='EN_COURS').aggregate(total=Sum('montant_accord'))['total'] or 0
    total_prets_rembourses_montant = prets_caisse.aggregate(total=Sum('montant_rembourse'))['total'] or 0
    nb_attente = prets_caisse.filter(statut__in=['EN_ATTENTE','EN_ATTENTE_ADMIN']).count()
    nb_en_cours = prets_caisse.filter(statut='EN_COURS').count()
    nb_rembourses = prets_caisse.filter(statut='REMBOURSE').count()
    nb_en_retard = prets_caisse.filter(statut='EN_RETARD').count()
    # Reste à rembourser (sur EN_COURS + EN_RETARD)
    restant_qs = prets_caisse.filter(statut__in=['EN_COURS','EN_RETARD']).annotate(
        restant=ExpressionWrapper((F('montant_accord') - F('montant_rembourse')), output_field=DecimalField(max_digits=15, decimal_places=2))
    )
    montant_restant = restant_qs.aggregate(total=Sum('restant'))['total'] or 0
    # Taux de remboursement
    taux_remb = float(total_prets_rembourses_montant)/float(total_prets_caisse) * 100 if float(total_prets_caisse) > 0 else 0.0
    # Appréciation
    if taux_remb >= 80:
        appreciation = 'Très bon'
    elif taux_remb >= 50:
        appreciation = 'Satisfaisant'
    else:
        appreciation = 'Faible'

    # Liste des prêts (membres) à afficher dans le PDF (états pertinents)
    prets_membres_qs = caisse.prets.select_related('membre').filter(
        statut__in=['EN_COURS', 'REMBOURSE', 'EN_RETARD']
    ).order_by('-date_demande')
    prets_membres = [
        {
            'membre': f"{p.membre.nom} {p.membre.prenoms}",
            'numero_pret': p.numero_pret,
            'montant_accord': float(p.montant_accord or 0),
            'montant_rembourse': float(p.montant_rembourse or 0),
            'statut': p.statut,
        }
        for p in prets_membres_qs
    ]

    return {
        'caisse': {
            'nom': caisse.nom_association,
            'code': caisse.code,
        },
        'fonds_actuels': {
            'fond_initial': float(caisse.fond_initial),
            'fond_disponible': float(caisse.fond_disponible),
            'montant_total_prets': float(total_prets_caisse),
            'montant_total_rembourse': float(total_prets_rembourses_montant),
            'montant_total_restant': float(montant_restant),
            'solde_disponible': float((caisse.fond_initial or 0) + (caisse.fond_disponible or 0)),
        },
        'prets_synthese': {
            'total_prets_montant': float(total_prets_caisse),
            'total_prets_rembourse_montant': float(total_prets_rembourses_montant),
            'total_prets_restant_montant': float(montant_restant),
            'nombre_en_attente': nb_attente,
            'nombre_en_cours': nb_en_cours,
            'nombre_en_retard': nb_en_retard,
            'nombre_rembourses': nb_rembourses,
            'taux_remboursement': round(taux_remb, 2),
            'appreciation': appreciation,
        },
        'prets_financiers': {
            'octroyes_total': float(total_prets_octroyes),
            'rembourses_total': float(prets_caisse.filter(statut='REMBOURSE').aggregate(total=Sum('montant_accord'))['total'] or 0),
        },
        'mouvements': {
            'stats_par_type': list(stats_mouvements),
            'evolution': evolution_fonds,
            'total_mouvements': mouvements.count(),
        },
        'prets_membres': prets_membres,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }


def generer_rapport_financier_global(date_debut=None, date_fin=None, caisses_qs=None):
    """Rapport financier agrégé pour un ensemble de caisses (toutes par défaut)."""
    from django.db.models import Sum, Q
    from django.utils import timezone
    start_dt = end_dt = None
    if date_debut:
        start_dt = timezone.make_aware(datetime.combine(date_debut, time.min), timezone.get_current_timezone())
    if date_fin:
        end_dt = timezone.make_aware(datetime.combine(date_fin, time.max), timezone.get_current_timezone())
    filtres_date = Q()
    if start_dt:
        filtres_date &= Q(date_mouvement__gte=start_dt)
    if end_dt:
        filtres_date &= Q(date_mouvement__lte=end_dt)

    caisses = caisses_qs if caisses_qs is not None else Caisse.objects.all()

    mouvements = MouvementFond.objects.filter(caisse__in=caisses).filter(filtres_date).order_by('-date_mouvement')
    stats_mouvements = list(
        mouvements.values('type_mouvement').annotate(total=Sum('montant'), nombre=Count('id'))
    )

    evolution_fonds = []
    # Pour global, on ne suit pas un solde précis; on liste l'évolution agrégée
    for mv in mouvements.order_by('date_mouvement'):
        evolution_fonds.append({
            'date': mv.date_mouvement.strftime('%d/%m/%Y'),
            'type': mv.type_mouvement,
            'montant': float(mv.montant),
            'solde': None,
            'description': mv.description,
        })

    from django.db.models import Sum as DSum, F, ExpressionWrapper, DecimalField
    from .models import Caisse, Pret
    # Agrégations robustes (montant_total_prets = EN_COURS + REMBOURSE + EN_RETARD)
    total_fond_initial = caisses.aggregate(total=DSum('fond_initial'))['total'] or 0
    total_fond_disponible = caisses.aggregate(total=DSum('fond_disponible'))['total'] or 0
    total_prets_accordes = Pret.objects.filter(caisse__in=caisses, statut__in=['EN_COURS', 'REMBOURSE', 'EN_RETARD']).aggregate(total=DSum('montant_accord'))['total'] or 0
    total_prets_rembourses = Pret.objects.filter(caisse__in=caisses, statut='REMBOURSE').aggregate(total=DSum('montant_accord'))['total'] or 0
    total_prets_octroyes = Pret.objects.filter(caisse__in=caisses, statut='EN_COURS').aggregate(total=DSum('montant_accord'))['total'] or 0
    restant_qs = Pret.objects.filter(caisse__in=caisses, statut__in=['EN_COURS', 'EN_RETARD']).annotate(
        restant=ExpressionWrapper((F('montant_accord') - F('montant_rembourse')), output_field=DecimalField(max_digits=15, decimal_places=2))
    )
    total_prets_restants = restant_qs.aggregate(total=DSum('restant'))['total'] or 0

    fonds_actuels = {
        'fond_initial': float(total_fond_initial),
        'fond_disponible': float(total_fond_disponible),
        'montant_total_prets': float(total_prets_accordes),
        'montant_total_rembourse': float(Pret.objects.filter(caisse__in=caisses).aggregate(total=DSum('montant_rembourse'))['total'] or 0),
        'montant_total_restant': float(total_prets_restants),
        'solde_disponible': float((total_fond_initial or 0) + (total_fond_disponible or 0)),
    }

    # Synthèse par caisse (pour affichage détaillé dans le PDF)
    par_caisse = []
    for c in caisses.order_by('nom_association'):
        total_prets_caisse = (
            (Pret.objects.filter(caisse=c, statut='EN_COURS').aggregate(total=Sum('montant_accord'))['total'] or 0)
            + (Pret.objects.filter(caisse=c, statut='REMBOURSE').aggregate(total=Sum('montant_accord'))['total'] or 0)
        )
        par_caisse.append({
            'code': c.code,
            'nom': c.nom_association,
            'fond_initial': float(c.fond_initial or 0),
            'fond_disponible': float(c.fond_disponible or 0),
            'montant_total_prets': float(total_prets_caisse),
            'solde_disponible': float((c.fond_initial or 0) + (c.fond_disponible or 0)),
        })

    prets_financiers = {
        'octroyes_total': float(total_prets_octroyes),
        'rembourses_total': float(total_prets_rembourses),
    }

    # Liste globale des prêts par membre (états pertinents)
    prets_globaux_qs = Pret.objects.select_related('membre', 'caisse').filter(
        statut__in=['EN_COURS', 'REMBOURSE', 'EN_RETARD']
    ).order_by('-date_demande')
    prets_membres = [
        {
            'caisse': p.caisse.nom_association if p.caisse else '-',
            'membre': f"{p.membre.nom} {p.membre.prenoms}",
            'numero_pret': p.numero_pret,
            'montant_accord': float(p.montant_accord or 0),
            'montant_rembourse': float(p.montant_rembourse or 0),
            'statut': p.statut,
        }
        for p in prets_globaux_qs
    ]

    return {
        'caisse': {'nom': 'Toutes les caisses', 'code': 'GLOBAL'},
        'fonds_actuels': fonds_actuels,
        'mouvements': {
            'stats_par_type': stats_mouvements,
            'evolution': evolution_fonds,
            'total_mouvements': mouvements.count(),
        },
        'par_caisse': par_caisse,
        'prets_financiers': prets_financiers,
        'prets_membres': prets_membres,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }

def generer_rapport_prets_caisse(caisse, date_debut=None, date_fin=None):
    """Génère un rapport détaillé des prêts de la caisse"""
    from django.db.models import Sum, Avg, Q
    from django.utils import timezone
    
    # Filtres de date
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_demande__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_demande__lte=date_fin)
    
    # Prêts avec détails
    prets = caisse.prets.filter(filtres_date).select_related('membre').prefetch_related('echeances')
    
    # Statistiques par statut
    stats_par_statut = prets.values('statut').annotate(
        nombre=Count('id'),
        montant_total=Sum('montant_accord'),
        montant_moyen=Avg('montant_accord')
    )
    
    # Statistiques par membre
    stats_par_membre = prets.values('membre__nom', 'membre__prenoms').annotate(
        nombre_prets=Count('id'),
        montant_total=Sum('montant_accord'),
        montant_rembourse=Sum('montant_rembourse')
    )
    
    # Prêts en retard
    prets_retard = prets.filter(statut='EN_RETARD').annotate(
        montant_retard=Sum('echeances__montant_echeance', filter=Q(echeances__statut='EN_RETARD'))
    )
    
    # Détails des prêts
    details_prets = []
    for pret in prets:
        details_prets.append({
            'numero': pret.numero_pret,
            'membre': f"{pret.membre.nom} {pret.membre.prenoms}",
            'montant_demande': float(pret.montant_demande),
            'montant_accord': float(pret.montant_accord) if pret.montant_accord else 0,
            'montant_rembourse': float(pret.montant_rembourse),
            'montant_restant': float(pret.montant_restant),
            'statut': pret.statut,
            'date_demande': pret.date_demande.strftime('%d/%m/%Y'),
            'date_decaissement': pret.date_decaissement.strftime('%d/%m/%Y') if pret.date_decaissement else None,
            'duree_mois': pret.duree_mois,
            'taux_interet': float(pret.taux_interet),
            'echeances_payees': pret.nombre_echeances_payees,
            'echeances_total': pret.nombre_echeances,
        })
    
    return {
        'caisse': {
            'nom': caisse.nom_association,
            'code': caisse.code,
        },
        'statistiques': {
            'par_statut': list(stats_par_statut),
            'par_membre': list(stats_par_membre),
        },
        'prets_retard': {
            'nombre': prets_retard.count(),
            'montant_total_retard': float(prets_retard.aggregate(total=Sum('montant_retard'))['total'] or 0),
        },
        'details_prets': details_prets,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }


def generer_rapport_prets_global(date_debut=None, date_fin=None, caisses_qs=None):
    """Rapport des prêts agrégé pour un ensemble de caisses (toutes par défaut)."""
    from django.db.models import Sum, Avg, Q
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_demande__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_demande__lte=date_fin)

    caisses = caisses_qs if caisses_qs is not None else Caisse.objects.all()

    prets = Pret.objects.filter(caisse__in=caisses).filter(filtres_date).select_related('membre', 'caisse')
    stats_par_statut = list(prets.values('statut').annotate(nombre=Count('id'), montant_total=Sum('montant_accord'), montant_moyen=Avg('montant_accord')))
    stats_par_caisse = list(prets.values('caisse__nom_association').annotate(nombre_prets=Count('id'), montant_total=Sum('montant_accord')))
    prets_retard = prets.filter(statut='EN_RETARD').annotate(montant_retard=Sum('echeances__montant_echeance', filter=Q(echeances__statut='EN_RETARD')))

    details_prets = []
    for pret in prets:
        details_prets.append({
            'numero': pret.numero_pret,
            'caisse': pret.caisse.nom_association,
            'membre': f"{pret.membre.nom} {pret.membre.prenoms}",
            'montant_demande': float(pret.montant_demande),
            'montant_accord': float(pret.montant_accord or 0),
            'montant_rembourse': float(pret.montant_rembourse or 0),
            'montant_restant': float(pret.montant_restant or 0),
            'statut': pret.statut,
            'date_demande': pret.date_demande.strftime('%d/%m/%Y'),
        })

    return {
        'caisse': {'nom': 'Toutes les caisses', 'code': 'GLOBAL'},
        'statistiques': {
            'par_statut': stats_par_statut,
            'par_caisse': stats_par_caisse,
        },
        'prets_retard': {
            'nombre': prets_retard.count(),
            'montant_total_retard': float(prets_retard.aggregate(total=Sum('montant_retard'))['total'] or 0),
        },
        'details_prets': details_prets,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }

def generer_rapport_membres_caisse(caisse, date_debut=None, date_fin=None):
    """Génère un rapport détaillé des membres de la caisse"""
    from django.db.models import Count, Sum, Q
    
    # Filtres de date
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_adhesion__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_adhesion__lte=date_fin)
    
    # Membres avec détails
    membres = caisse.membres.filter(filtres_date)
    
    # Statistiques par statut
    stats_par_statut = membres.values('statut').annotate(
        nombre=Count('id')
    )
    
    # Statistiques par sexe
    stats_par_sexe = membres.values('sexe').annotate(
        nombre=Count('id')
    )
    
    # Statistiques par rôle
    stats_par_role = membres.values('role').annotate(
        nombre=Count('id')
    )
    
    # Membres avec prêts
    membres_avec_prets = membres.annotate(
        nombre_prets=Count('prets'),
        montant_total_prets=Sum('prets__montant_accord'),
        montant_total_rembourse=Sum('prets__montant_rembourse')
    )
    
    # Détails des membres
    details_membres = []
    for membre in membres_avec_prets:
        details_membres.append({
            'nom_complet': f"{membre.nom} {membre.prenoms}",
            'numero_carte': membre.numero_carte_electeur,
            'telephone': membre.numero_telephone,
            'sexe': membre.sexe,
            'role': membre.role,
            'statut': membre.statut,
            'date_adhesion': membre.date_adhesion.strftime('%d/%m/%Y'),
            'nombre_prets': membre.nombre_prets,
            'montant_total_prets': float(membre.montant_total_prets or 0),
            'montant_total_rembourse': float(membre.montant_total_rembourse or 0),
        })
    
    return {
        'caisse': {
            'nom': caisse.nom_association,
            'code': caisse.code,
        },
        'statistiques': {
            'par_statut': list(stats_par_statut),
            'par_sexe': list(stats_par_sexe),
            'par_role': list(stats_par_role),
        },
        'details_membres': details_membres,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }


def generer_rapport_membres_global(date_debut=None, date_fin=None, caisses_qs=None):
    """Rapport membres agrégé pour un ensemble de caisses (toutes par défaut)."""
    from django.db.models import Count, Sum, Q
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_adhesion__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_adhesion__lte=date_fin)

    caisses = caisses_qs if caisses_qs is not None else Caisse.objects.all()

    membres = Membre.objects.filter(caisse__in=caisses).filter(filtres_date)
    stats_par_statut = list(membres.values('statut').annotate(nombre=Count('id')))
    stats_par_sexe = list(membres.values('sexe').annotate(nombre=Count('id')))
    stats_par_role = list(membres.values('role').annotate(nombre=Count('id')))

    membres_avec_prets = membres.annotate(
        nombre_prets=Count('prets'),
        montant_total_prets=Sum('prets__montant_accord'),
        montant_total_rembourse=Sum('prets__montant_rembourse')
    )
    details_membres = []
    for m in membres_avec_prets.select_related('caisse'):
        details_membres.append({
            'caisse': m.caisse.nom_association if m.caisse else '-',
            'nom_complet': f"{m.nom} {m.prenoms}",
            'numero_carte': m.numero_carte_electeur,
            'telephone': m.numero_telephone,
            'sexe': m.sexe,
            'role': m.role,
            'statut': m.statut,
            'date_adhesion': m.date_adhesion.strftime('%d/%m/%Y') if m.date_adhesion else None,
            'nombre_prets': m.nombre_prets,
            'montant_total_prets': float(m.montant_total_prets or 0),
            'montant_total_rembourse': float(m.montant_total_rembourse or 0),
        })

    return {
        'caisse': {'nom': 'Toutes les caisses', 'code': 'GLOBAL'},
        'statistiques': {
            'par_statut': stats_par_statut,
            'par_sexe': stats_par_sexe,
            'par_role': stats_par_role,
        },
        'details_membres': details_membres,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }

def generer_rapport_echeances_caisse(caisse, date_debut=None, date_fin=None):
    """Génère un rapport détaillé des échéances de la caisse"""
    from django.db.models import Sum, Q
    from django.utils import timezone
    
    # Filtres de date
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_echeance__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_echeance__lte=date_fin)
    
    # Échéances avec détails
    echeances = Echeance.objects.filter(
        pret__caisse=caisse
    ).filter(filtres_date).select_related('pret', 'pret__membre')
    
    # Statistiques par statut
    stats_par_statut = echeances.values('statut').annotate(
        nombre=Count('id'),
        montant_total=Sum('montant_echeance'),
        montant_paye=Sum('montant_paye')
    )
    
    # Échéances en retard
    echeances_retard = echeances.filter(
        date_echeance__lt=timezone.now().date(),
        statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
    )
    
    # Échéances à venir (prochaines 30 jours)
    date_limite = timezone.now().date() + timedelta(days=30)
    echeances_a_venir = echeances.filter(
        date_echeance__lte=date_limite,
        statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE']
    )
    
    # Détails des échéances
    details_echeances = []
    for echeance in echeances:
        details_echeances.append({
            'numero_echeance': echeance.numero_echeance,
            'pret_numero': echeance.pret.numero_pret,
            'membre': f"{echeance.pret.membre.nom} {echeance.pret.membre.prenoms}",
            'montant_echeance': float(echeance.montant_echeance),
            'montant_paye': float(echeance.montant_paye),
            'montant_restant': float(echeance.montant_echeance - echeance.montant_paye),
            'date_echeance': echeance.date_echeance.strftime('%d/%m/%Y'),
            'date_paiement': echeance.date_paiement.strftime('%d/%m/%Y') if echeance.date_paiement else None,
            'statut': echeance.statut,
            'en_retard': echeance.date_echeance < timezone.now().date() and echeance.statut in ['A_PAYER', 'PARTIELLEMENT_PAYE'],
        })
    
    return {
        'caisse': {
            'nom': caisse.nom_association,
            'code': caisse.code,
        },
        'statistiques': {
            'par_statut': list(stats_par_statut),
            'total_echeances': echeances.count(),
            'total_montant': float(echeances.aggregate(total=Sum('montant_echeance'))['total'] or 0),
            'total_paye': float(echeances.aggregate(total=Sum('montant_paye'))['total'] or 0),
        },
        'echeances_retard': {
            'nombre': echeances_retard.count(),
            'montant_total': float(echeances_retard.aggregate(total=Sum('montant_echeance'))['total'] or 0),
        },
        'echeances_a_venir': {
            'nombre': echeances_a_venir.count(),
            'montant_total': float(echeances_a_venir.aggregate(total=Sum('montant_echeance'))['total'] or 0),
        },
        'details_echeances': details_echeances,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }


def generer_rapport_echeances_global(date_debut=None, date_fin=None, caisses_qs=None):
    """Rapport échéances agrégé pour un ensemble de caisses (toutes par défaut)."""
    from django.db.models import Sum, Q
    from django.utils import timezone
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_echeance__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_echeance__lte=date_fin)

    caisses = caisses_qs if caisses_qs is not None else Caisse.objects.all()

    echeances = Echeance.objects.filter(pret__caisse__in=caisses).filter(filtres_date).select_related('pret', 'pret__membre', 'pret__caisse')
    stats_par_statut = list(echeances.values('statut').annotate(nombre=Count('id'), montant_total=Sum('montant_echeance'), montant_paye=Sum('montant_paye')))
    echeances_retard = echeances.filter(date_echeance__lt=timezone.now().date(), statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE'])
    date_limite = timezone.now().date() + timedelta(days=30)
    echeances_a_venir = echeances.filter(date_echeance__lte=date_limite, statut__in=['A_PAYER', 'PARTIELLEMENT_PAYE'])

    details_echeances = []
    for e in echeances:
        details_echeances.append({
            'caisse': e.pret.caisse.nom_association,
            'numero_echeance': e.numero_echeance,
            'pret_numero': e.pret.numero_pret,
            'membre': f"{e.pret.membre.nom} {e.pret.membre.prenoms}",
            'montant_echeance': float(e.montant_echeance),
            'montant_paye': float(e.montant_paye),
            'montant_restant': float(e.montant_echeance - e.montant_paye),
            'date_echeance': e.date_echeance.strftime('%d/%m/%Y'),
            'date_paiement': e.date_paiement.strftime('%d/%m/%Y') if e.date_paiement else None,
            'statut': e.statut,
            'en_retard': e.date_echeance < timezone.now().date() and e.statut in ['A_PAYER', 'PARTIELLEMENT_PAYE'],
        })

    return {
        'caisse': {'nom': 'Toutes les caisses', 'code': 'GLOBAL'},
        'statistiques': {
            'par_statut': stats_par_statut,
            'total_echeances': echeances.count(),
            'total_montant': float(echeances.aggregate(total=Sum('montant_echeance'))['total'] or 0),
            'total_paye': float(echeances.aggregate(total=Sum('montant_paye'))['total'] or 0),
        },
        'echeances_retard': {
            'nombre': echeances_retard.count(),
            'montant_total': float(echeances_retard.aggregate(total=Sum('montant_echeance'))['total'] or 0),
        },
        'echeances_a_venir': {
            'nombre': echeances_a_venir.count(),
            'montant_total': float(echeances_a_venir.aggregate(total=Sum('montant_echeance'))['total'] or 0),
        },
        'details_echeances': details_echeances,
        'periode': {
            'debut': date_debut.strftime('%d/%m/%Y') if date_debut else None,
            'fin': date_fin.strftime('%d/%m/%Y') if date_fin else None,
        }
    }

# Vues pour la génération des PDFs d'attestation
@login_required
def generate_attestation_pret_pdf(request, pret_id):
    """Génère et télécharge le PDF d'attestation d'octroi de prêt"""
    try:
        pret = Pret.objects.get(id=pret_id)
        
        # Vérifier les permissions (seuls les membres de la caisse ou les admins peuvent voir)
        user_caisse = get_user_caisse(request.user)
        if not request.user.is_superuser and (not user_caisse or user_caisse.id != pret.caisse.id):
            messages.error(request, "Vous n'avez pas l'autorisation de voir ce prêt.")
            return redirect('gestion_caisses:dashboard')
        
        # Générer le PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="attestation_pret_{pret.numero_pret}.pdf"'
        
        # Appeler la fonction de génération du PDF
        generate_pret_octroi_pdf(pret, response)
        
        return response
        
    except Pret.DoesNotExist:
        messages.error(request, "Prêt non trouvé.")
        return redirect('gestion_caisses:dashboard')
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
        return redirect('gestion_caisses:dashboard')


@login_required
def generate_attestation_remboursement_pdf(request, pret_id):
    """Génère et télécharge le PDF d'attestation de remboursement complet"""
    try:
        pret = Pret.objects.get(id=pret_id)
        
        # Vérifier les permissions (seuls les membres de la caisse ou les admins peuvent voir)
        user_caisse = get_user_caisse(request.user)
        if not request.user.is_superuser and (not user_caisse or user_caisse.id != pret.caisse.id):
            messages.error(request, "Vous n'avez pas l'autorisation de voir ce prêt.")
            return redirect('gestion_caisses:dashboard')
        
        # Vérifier que le prêt est bien remboursé
        if pret.statut != 'REMBOURSE':
            messages.error(request, "Ce prêt n'est pas encore complètement remboursé.")
            return redirect('gestion_caisses:dashboard')
        
        # Récupérer les mouvements de remboursement
        from .models import MouvementFond
        mouvements_remboursement = MouvementFond.objects.filter(
            pret=pret,
            type_mouvement='REMBOURSEMENT'
        ).order_by('date_mouvement')

        if not mouvements_remboursement.exists():
            messages.error(request, "Aucun mouvement de remboursement trouvé pour ce prêt.")
            return redirect('gestion_caisses:dashboard')

        # Générer le PDF
        pdf = generate_remboursement_complet_pdf(pret, mouvements_remboursement)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="attestation_remboursement_{pret.numero_pret}.pdf"'
        return response
        
    except Pret.DoesNotExist:
        messages.error(request, "Prêt non trouvé.")
        return redirect('gestion_caisses:dashboard')


@login_required
def generate_application_guide(request):
    """Télécharger le guide complet de l'application en PDF."""
    try:
        pdf = generate_application_guide_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="guide_application.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
        return redirect('gestion_caisses:dashboard')
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
        return redirect('gestion_caisses:dashboard')


class TransfertCaisseViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des transferts entre caisses"""
    queryset = TransfertCaisse.objects.select_related(
        'caisse_source', 'caisse_destination', 'utilisateur', 
        'mouvement_source', 'mouvement_destination'
    ).all()
    serializer_class = TransfertCaisseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_transfert', 'statut', 'caisse_source', 'caisse_destination']
    search_fields = ['description', 'caisse_source__nom_association', 'caisse_destination__nom_association']
    ordering_fields = ['date_transfert', 'montant']
    ordering = ['-date_transfert']
    
    def get_queryset(self):
        """Filtrer les transferts selon les permissions de l'utilisateur"""
        queryset = super().get_queryset()
        
        # Si l'utilisateur n'est pas admin, filtrer par ses caisses
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                caisse_ids = user_caisses.values_list('id', flat=True)
                queryset = queryset.filter(
                    models.Q(caisse_source_id__in=caisse_ids) | 
                    models.Q(caisse_destination_id__in=caisse_ids)
                )
            else:
                queryset = queryset.none()
        
        return queryset
    
    @action(detail=True, methods=['post'], url_path='executer')
    def executer_transfert(self, request, pk=None):
        """Exécuter un transfert en attente"""
        transfert = self.get_object()
        
        if transfert.statut != 'EN_ATTENTE':
            return Response(
                {'error': f'Le transfert est déjà en statut {transfert.get_statut_display()}'},
                status=400
            )
        
        try:
            transfert.executer_transfert()
            return Response({
                'message': 'Transfert exécuté avec succès',
                'statut': transfert.statut
            })
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de l\'exécution du transfert: {str(e)}'},
                status=400
            )
    
    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler_transfert(self, request, pk=None):
        """Annuler un transfert validé"""
        transfert = self.get_object()
        
        if transfert.statut != 'VALIDE':
            return Response(
                {'error': f'Seuls les transferts validés peuvent être annulés'},
                status=400
            )
        
        try:
            transfert.annuler_transfert()
            return Response({
                'message': 'Transfert annulé avec succès',
                'statut': transfert.statut
            })
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de l\'annulation du transfert: {str(e)}'},
                status=400
            )
    
    @action(detail=False, methods=['get'], url_path='statistiques')
    def statistiques_transferts(self, request):
        """Obtenir des statistiques sur les transferts"""
        queryset = self.get_queryset()
        
        # Statistiques par type de transfert
        stats_par_type = queryset.values('type_transfert').annotate(
            total_montant=Sum('montant'),
            nombre_transferts=Count('id'),
            montant_moyen=Avg('montant')
        )
        
        # Statistiques par statut
        stats_par_statut = queryset.values('statut').annotate(
            total_montant=Sum('montant'),
            nombre_transferts=Count('id')
        )
        
        # Évolution des transferts (6 derniers mois)
        evolution_transferts = []
        for i in range(6):
            date = timezone.now() - timedelta(days=30*i)
            mois = date.strftime('%Y-%m')
            count = queryset.filter(date_transfert__year=date.year, date_transfert__month=date.month).count()
            montant_total = queryset.filter(
                date_transfert__year=date.year, 
                date_transfert__month=date.month
            ).aggregate(total=Sum('montant'))['total'] or 0
            
            evolution_transferts.append({
                'mois': mois, 
                'nombre': count,
                'montant_total': float(montant_total)
            })
        
        return Response({
            'stats_par_type': list(stats_par_type),
            'stats_par_statut': list(stats_par_statut),
            'evolution_transferts': evolution_transferts,
            'total_transferts': queryset.count(),
            'montant_total_transferts': float(queryset.aggregate(total=Sum('montant'))['total'] or 0)
        })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Vue pour la consultation des journaux d'audit (lecture seule)"""
    queryset = AuditLog.objects.select_related('utilisateur').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]  # Seuls les administrateurs peuvent consulter les logs
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['action', 'modele', 'utilisateur']
    search_fields = ['modele', 'details']
    ordering_fields = ['date_action', 'action']
    ordering = ['-date_action']

# ============================================================================
# VUES POUR RAPPORTS ET ÉTATS ADMIN
# ============================================================================

@login_required
def rapport_general_view(request):
    """Vue pour générer le rapport général du système"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les paramètres de la requête
    format_output = request.GET.get('format', 'html')
    caisse_id = request.GET.get('caisse')
    date_debut_str = request.GET.get('date_debut')
    date_fin_str = request.GET.get('date_fin')
    
    # Convertir les dates
    date_debut = None
    date_fin = None
    if date_debut_str:
        try:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if date_fin_str:
        try:
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Utiliser la fonction de génération globale
    data = generer_rapport_general_global(date_debut, date_fin)
    
    # Si format PDF demandé
    if format_output == 'pdf':
        # Créer un rapport temporaire pour le PDF
        rapport = RapportActivite(
            type_rapport='general',
            caisse_id=caisse_id if caisse_id else None,
            date_debut=date_debut,
            date_fin=date_fin,
            statut='EN_ATTENTE',
            genere_par=request.user,
            donnees=data
        )
        try:
            pdf_content = generate_rapport_pdf(rapport)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="rapport_general_{date_debut or "all"}_{date_fin or "all"}.pdf"'
            return response
        except Exception as e:
            messages.error(request, f'Erreur lors de la génération du PDF: {str(e)}')
            # Continuer avec le rendu HTML en cas d'erreur
    
    # Préparer le contexte pour le template HTML
    from django.utils import timezone
    today = timezone.now().date()
    
    context = {
        'user': request.user,
        'date_generation': today,
        'data': data,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'format': format_output,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_general.html', context)


@login_required
def rapport_financier_view(request):
    """Vue pour générer le rapport financier complet"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données financières
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    # Fonds des caisses
    caisses = Caisse.objects.filter(statut='ACTIVE').annotate(
        total_prets=Count('prets'),
        prets_actifs=Count('prets', filter=Q(prets__statut='EN_COURS')),
        total_montant_prets=Sum('prets__montant_accord'),
        total_montant_rembourse=Sum('prets__montant_rembourse')
    )
    
    # Mouvements de fonds
    mouvements = MouvementFond.objects.select_related('caisse').filter(
        date_mouvement__gte=last_month
    ).order_by('-date_mouvement')
    
    # Statistiques par type de mouvement
    stats_mouvements = mouvements.values('type_mouvement').annotate(
        total=Sum('montant'),
        nombre=Count('id')
    )
    
    # Caisse générale
    try:
        caisse_generale = CaisseGenerale.get_instance()
        solde_reserve = caisse_generale.solde_reserve
        solde_systeme = caisse_generale.solde_systeme
        solde_total_caisses = caisse_generale.solde_total_caisses
    except:
        solde_reserve = 0
        solde_systeme = 0
        solde_total_caisses = 0
    
    context = {
        'user': request.user,
        'date_generation': today,
        'caisses': caisses,
        'mouvements': mouvements,
        'stats_mouvements': stats_mouvements,
        'solde_reserve': solde_reserve,
        'solde_systeme': solde_systeme,
        'solde_total_caisses': solde_total_caisses,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_financier.html', context)


@login_required
def rapport_prets_view(request):
    """Vue pour générer le rapport des prêts"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des prêts
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    # Prêts avec détails
    prets = Pret.objects.select_related('membre', 'caisse').annotate(
        total_echeances=Count('echeances'),
        echeances_payees=Count('echeances', filter=Q(echeances__statut='PAYEE'))
    ).order_by('-date_demande')
    
    # Statistiques par statut
    stats_par_statut = prets.values('statut').annotate(
        total=Count('id'),
        montant_total=Sum('montant_accord'),
        montant_rembourse=Sum('montant_rembourse')
    )
    
    # Statistiques par caisse
    stats_par_caisse = prets.values('caisse__nom_association').annotate(
        total=Count('id'),
        montant_total=Sum('montant_accord'),
        montant_rembourse=Sum('montant_rembourse')
    )
    
    # Prêts en retard
    prets_en_retard = prets.filter(
        echeances__date_echeance__lt=today,
        echeances__statut='EN_ATTENTE',
        statut='EN_COURS'
    ).distinct()
    
    context = {
        'user': request.user,
        'date_generation': today,
        'prets': prets,
        'stats_par_statut': stats_par_statut,
        'stats_par_caisse': stats_par_caisse,
        'prets_en_retard': prets_en_retard,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_prets.html', context)


@login_required
def rapport_membres_view(request):
    """Vue pour générer le rapport des membres"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des membres
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    # Membres avec statistiques
    membres = Membre.objects.filter(statut='ACTIF').annotate(
        total_prets=Count('prets'),
        prets_actifs=Count('prets', filter=Q(prets__statut='EN_COURS')),
        montant_total_prets=Sum('prets__montant_accord'),
        montant_total_rembourse=Sum('prets__montant_rembourse')
    ).order_by('nom', 'prenoms')
    
    # Statistiques par région
    stats_par_region = membres.values('caisse__region__nom').annotate(
        total=Count('id'),
        nombre_prets=Sum('prets__id'),
        montant_prets=Sum('prets__montant_accord')
    )
    
    # Statistiques par préfecture
    stats_par_prefecture = membres.values('caisse__prefecture__nom').annotate(
        total=Count('id'),
        nombre_prets=Sum('prets__id'),
        montant_prets=Sum('prets__montant_accord')
    )
    
    context = {
        'user': request.user,
        'date_generation': today,
        'membres': membres,
        'stats_par_region': stats_par_region,
        'stats_par_prefecture': stats_par_prefecture,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_membres.html', context)


@login_required
def rapport_transferts_view(request):
    """Vue pour générer le rapport des transferts"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des transferts
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    # Transferts avec détails
    try:
        transferts = TransfertCaisse.objects.select_related(
            'caisse_source', 'caisse_destination', 'utilisateur'
        ).order_by('-date_transfert')
        
        # Statistiques par type
        stats_par_type = transferts.values('type_transfert').annotate(
            total=Count('id'),
            montant_total=Sum('montant')
        )
        
        # Statistiques par statut
        stats_par_statut = transferts.values('statut').annotate(
            total=Count('id'),
            montant_total=Sum('montant')
        )
        
        # Statistiques par caisse source
        stats_par_caisse_source = transferts.values('caisse_source__nom_association').annotate(
            total=Count('id'),
            montant_total=Sum('montant')
        )
        
    except:
        transferts = []
        stats_par_type = []
        stats_par_statut = []
        stats_par_caisse_source = []
    
    context = {
        'user': request.user,
        'date_generation': today,
        'transferts': transferts,
        'stats_par_type': stats_par_type,
        'stats_par_statut': stats_par_statut,
        'stats_par_caisse_source': stats_par_caisse_source,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_transferts.html', context)


@login_required
def rapport_caisses_view(request):
    """Vue pour générer le rapport des caisses"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des caisses
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    # Caisses avec statistiques
    caisses = Caisse.objects.filter(statut='ACTIVE').annotate(
        total_membres=Count('membres'),
        total_prets=Count('prets'),
        prets_actifs=Count('prets', filter=Q(prets__statut='EN_COURS')),
        total_montant_prets=Sum('prets__montant_accord'),
        total_montant_rembourse=Sum('prets__montant_rembourse')
    ).order_by('nom_association')
    
    # Statistiques par région
    stats_par_region = caisses.values('region__nom').annotate(
        total=Count('id'),
        total_fonds=Sum('fond_disponible'),
        total_membres=Sum('membres'),
        total_prets=Sum('prets')
    )
    
    # Statistiques par préfecture
    stats_par_prefecture = caisses.values('prefecture__nom').annotate(
        total=Count('id'),
        total_fonds=Sum('fond_disponible'),
        total_membres=Sum('membres'),
        total_prets=Sum('prets')
    )
    
    context = {
        'user': request.user,
        'date_generation': today,
        'caisses': caisses,
        'stats_par_region': stats_par_region,
        'stats_par_prefecture': stats_par_prefecture,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_caisses.html', context)


@login_required
def rapport_audit_view(request):
    """Vue pour générer le rapport d'audit"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données d'audit
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    # Logs d'audit
    logs = AuditLog.objects.select_related('utilisateur').filter(
        date_action__gte=last_month
    ).order_by('-date_action')
    
    # Statistiques par action
    stats_par_action = logs.values('action').annotate(
        total=Count('id')
    )
    
    # Statistiques par modèle
    stats_par_modele = logs.values('modele').annotate(
        total=Count('id')
    )
    
    # Statistiques par utilisateur
    stats_par_utilisateur = logs.values('utilisateur__username').annotate(
        total=Count('id')
    ).filter(utilisateur__isnull=False)
    
    context = {
        'user': request.user,
        'date_generation': today,
        'logs': logs,
        'stats_par_action': stats_par_action,
        'stats_par_modele': stats_par_modele,
        'stats_par_utilisateur': stats_par_utilisateur,
    }
    
    return render(request, 'gestion_caisses/rapports/rapport_audit.html', context)


# ============================================================================
# VUES POUR IMPRESSION DES ÉTATS
# ============================================================================

@login_required
def etat_general_print_view(request):
    """Vue pour imprimer l'état général du système"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données pour l'impression
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Données générales
    total_caisses = Caisse.objects.count()
    total_membres = Membre.objects.count()
    total_prets = Pret.objects.count()
    total_fonds = Caisse.objects.aggregate(total=Sum('fond_disponible'))['total'] or 0
    
    # Caisse générale
    try:
        caisse_generale = CaisseGenerale.get_instance()
        solde_reserve = caisse_generale.solde_reserve
        solde_systeme = caisse_generale.solde_systeme
    except:
        solde_reserve = 0
        solde_systeme = 0
    
    context = {
        'user': request.user,
        'date_generation': today,
        'total_caisses': total_caisses,
        'total_membres': total_membres,
        'total_prets': total_prets,
        'total_fonds': total_fonds,
        'solde_reserve': solde_reserve,
        'solde_systeme': solde_systeme,
    }
    
    response = render(request, 'gestion_caisses/impression/etat_general.html', context)
    response['Content-Type'] = 'text/html; charset=utf-8'
    return response


@login_required
def etat_financier_print_view(request):
    """Vue pour imprimer l'état financier"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données financières
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Caisses avec détails
    caisses = Caisse.objects.filter(statut='ACTIVE').annotate(
        total_membres=Count('membres'),
        total_prets=Count('prets'),
        total_montant_prets=Sum('prets__montant_accord'),
        total_montant_rembourse=Sum('prets__montant_rembourse')
    ).order_by('nom_association')
    
    # Caisse générale
    try:
        caisse_generale = CaisseGenerale.get_instance()
        solde_reserve = caisse_generale.solde_reserve
        solde_systeme = caisse_generale.solde_systeme
    except:
        solde_reserve = 0
        solde_systeme = 0
    
    context = {
        'user': request.user,
        'date_generation': today,
        'caisses': caisses,
        'solde_reserve': solde_reserve,
        'solde_systeme': solde_systeme,
    }
    
    response = render(request, 'gestion_caisses/impression/etat_financier.html', context)
    response['Content-Type'] = 'text/html; charset=utf-8'
    return response


@login_required
def etat_prets_print_view(request):
    """Vue pour imprimer l'état des prêts"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des prêts
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Prêts avec détails
    prets = Pret.objects.select_related('membre', 'caisse').annotate(
        total_echeances=Count('echeances'),
        echeances_payees=Count('echeances', filter=Q(echeances__statut='PAYEE'))
    ).order_by('-date_demande')
    
    # Statistiques
    total_prets = prets.count()
    prets_en_cours = prets.filter(statut='EN_COURS').count()
    prets_rembourses = prets.filter(statut='REMBOURSE').count()
    total_montant = prets.aggregate(total=Sum('montant_accord'))['total'] or 0
    total_rembourse = prets.aggregate(total=Sum('montant_rembourse'))['total'] or 0
    
    context = {
        'user': request.user,
        'date_generation': today,
        'prets': prets,
        'total_prets': total_prets,
        'prets_en_cours': prets_en_cours,
        'prets_rembourses': prets_rembourses,
        'total_montant': total_montant,
        'total_rembourse': total_rembourse,
    }
    
    response = render(request, 'gestion_caisses/impression/etat_prets.html', context)
    response['Content-Type'] = 'text/html; charset=utf-8'
    return response


@login_required
def etat_caisses_print_view(request):
    """Vue pour imprimer l'état des caisses"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des caisses
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Caisses avec statistiques
    caisses = Caisse.objects.filter(statut='ACTIVE').annotate(
        total_membres=Count('membres'),
        total_prets=Count('prets'),
        total_montant_prets=Sum('prets__montant_accord'),
        total_montant_rembourse=Sum('prets__montant_rembourse')
    ).order_by('nom_association')
    
    context = {
        'user': request.user,
        'date_generation': today,
        'caisses': caisses,
    }
    
    response = render(request, 'gestion_caisses/impression/etat_caisses.html', context)
    response['Content-Type'] = 'text/html; charset=utf-8'
    return response


@login_required
def etat_transferts_print_view(request):
    """Vue pour imprimer l'état des transferts"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Récupérer les données des transferts
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    
    today = timezone.now().date()
    
    try:
        # Transferts avec détails
        transferts = TransfertCaisse.objects.select_related(
            'caisse_source', 'caisse_destination', 'utilisateur'
        ).order_by('-date_transfert')
        
        # Statistiques
        total_transferts = transferts.count()
        transferts_valides = transferts.filter(statut='VALIDE').count()
        montant_total = transferts.filter(statut='VALIDE').aggregate(total=Sum('montant'))['total'] or 0
        
    except:
        transferts = []
        total_transferts = 0
        transferts_valides = 0
        montant_total = 0
    
    context = {
        'user': request.user,
        'date_generation': today,
        'transferts': transferts,
        'total_transferts': total_transferts,
        'transferts_valides': transferts_valides,
        'montant_total': montant_total,
    }
    
    response = render(request, 'gestion_caisses/impression/etat_transferts.html', context)
    response['Content-Type'] = 'text/html; charset=utf-8'
    return response


# ============================================================================
# VUES POUR EXPORT ET TÉLÉCHARGEMENT
# ============================================================================

@login_required
def export_rapport_pdf_view(request, type_rapport):
    """Vue pour exporter un rapport en PDF"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Logique d'export PDF selon le type de rapport
    # À implémenter avec ReportLab ou WeasyPrint
    
    return HttpResponse("Export PDF en cours de développement")


# ============================================================================
# VUES POUR MAINTENANCE ET SYSTÈME
# ============================================================================

@login_required
def synchroniser_systeme_view(request):
    """Vue pour synchroniser le système"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    try:
        # Synchroniser la caisse générale
        caisse_generale = CaisseGenerale.get_instance()
        caisse_generale.recalculer_total_caisses()
        
        messages.success(request, "Système synchronisé avec succès !")
    except Exception as e:
        messages.error(request, f"Erreur lors de la synchronisation : {str(e)}")
    
    return redirect('admin:gestion_caisses_admindashboard_changelist')


@login_required
def verifier_integrite_view(request):
    """Vue pour vérifier l'intégrité du système"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Logique de vérification d'intégrité
    # À implémenter selon les besoins
    
    messages.info(request, "Vérification d'intégrité en cours de développement")
    return redirect('admin:gestion_caisses_admindashboard_changelist')


@login_required
def nettoyer_donnees_view(request):
    """Vue pour nettoyer les données du système"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Logique de nettoyage des données
    # À implémenter selon les besoins
    
    messages.info(request, "Nettoyage des données en cours de développement")
    return redirect('admin:gestion_caisses_admindashboard_changelist')


@login_required
def sauvegarder_systeme_view(request):
    """Vue pour sauvegarder le système"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    # Logique de sauvegarde du système
    # À implémenter selon les besoins
    
    messages.info(request, "Sauvegarde du système en cours de développement")
    return redirect('admin:gestion_caisses_admindashboard_changelist')


# ============================================================================
# FRONTEND ADMIN PERSONNALISÉ (rapports/états)
# ============================================================================

# ============================================================================
# VUES POUR LA GÉNÉRATION DES RAPPORTS PDF
# ============================================================================

@staff_member_required
def generer_rapport_pdf_admin(request):
    """Vue admin pour générer des rapports PDF"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Méthode non autorisée'}, status=405)
    
    try:
        # Vérifier le token CSRF
        if not request.headers.get('X-CSRFToken'):
            return JsonResponse({'success': False, 'message': 'Token CSRF manquant'}, status=403)
        
        # Récupérer les données JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Données JSON invalides'}, status=400)
        
        # Validation des données
        type_rapport = data.get('type_rapport')
        if not type_rapport:
            return JsonResponse({'success': False, 'message': 'Type de rapport requis'}, status=400)
        
        date_debut = data.get('date_debut')
        date_fin = data.get('date_fin')
        if not date_debut or not date_fin:
            return JsonResponse({'success': False, 'message': 'Dates de début et fin requises'}, status=400)
        
        # Convertir les dates
        try:
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Format de date invalide'}, status=400)
        
        # Récupérer la caisse si spécifiée
        caisse = None
        if data.get('caisse'):
            try:
                caisse = Caisse.objects.get(pk=data['caisse'])
            except Caisse.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Caisse introuvable'}, status=404)
        
        # Créer le rapport
        rapport = RapportActivite.objects.create(
            type_rapport=type_rapport,
            caisse=caisse,
            date_debut=date_debut,
            date_fin=date_fin,
            notes=data.get('notes', ''),
            statut='EN_ATTENTE',
            genere_par=request.user
        )
        
        # Générer le PDF
        try:
            pdf_content = generate_rapport_pdf(rapport)
            
            # Sauvegarder le fichier
            filename = f"rapport_{type_rapport}_{rapport.pk}.pdf"
            rapport.fichier_pdf.save(filename, ContentFile(pdf_content), save=True)
            
            rapport.statut = 'GENERE'
            rapport.date_generation = timezone.now()
            rapport.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Rapport généré avec succès',
                'rapport_id': rapport.pk,
                'pdf_url': rapport.fichier_pdf.url
            })
            
        except Exception as e:
            rapport.statut = 'ECHEC'
            rapport.notes = f"Erreur lors de la génération: {str(e)}"
            rapport.save()
            
            return JsonResponse({
                'success': False,
                'message': f'Erreur lors de la génération du PDF: {str(e)}'
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erreur inattendue: {str(e)}'
        }, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def telecharger_rapport_pdf(request, rapport_id):
    """Télécharge un rapport PDF"""
    try:
        rapport = get_object_or_404(RapportActivite, pk=rapport_id)
        
        if not rapport.fichier_pdf:
            messages.error(request, 'Ce rapport n\'a pas de fichier PDF.')
            return redirect('admin:gestion_caisses_rapportactivite_changelist')
        
        if rapport.statut != 'GENERE':
            messages.warning(request, 'Ce rapport n\'est pas encore généré.')
            return redirect('admin:gestion_caisses_rapportactivite_changelist')
        
        # Vérifier que le fichier existe
        if not os.path.exists(rapport.fichier_pdf.path):
            messages.error(request, 'Le fichier PDF n\'existe plus sur le serveur.')
            return redirect('admin:gestion_caisses_rapportactivite_changelist')
        
        # Lire et retourner le fichier
        with open(rapport.fichier_pdf.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="rapport_{rapport.type_rapport}_{rapport.pk}.pdf"'
            return response
            
    except Exception as e:
        messages.error(request, f'Erreur lors du téléchargement: {str(e)}')
        return redirect('admin:gestion_caisses_rapportactivite_changelist')

@login_required
@user_passes_test(lambda u: u.is_staff)
def previsualiser_rapport_pdf(request, rapport_id):
    """Prévisualise un rapport PDF dans le navigateur"""
    try:
        rapport = get_object_or_404(RapportActivite, pk=rapport_id)
        
        if not rapport.fichier_pdf:
            messages.error(request, 'Ce rapport n\'a pas de fichier PDF.')
            return redirect('admin:gestion_caisses_rapportactivite_changelist')
        
        if rapport.statut != 'GENERE':
            messages.warning(request, 'Ce rapport n\'est pas encore généré.')
            return redirect('admin:gestion_caisses_rapportactivite_changelist')
        
        # Vérifier que le fichier existe
        if not os.path.exists(rapport.fichier_pdf.path):
            messages.error(request, 'Le fichier PDF n\'existe plus sur le serveur.')
            return redirect('admin:gestion_caisses_rapportactivite_changelist')
        
        # Lire et retourner le fichier pour prévisualisation
        with open(rapport.fichier_pdf.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = 'inline'
            return response
            
    except Exception as e:
        messages.error(request, f'Erreur lors de la prévisualisation: {str(e)}')
        return redirect('admin:gestion_caisses_rapportactivite_changelist')

@login_required
@user_passes_test(lambda u: u.is_staff)
def lister_caisses_rapport(request):
    """Retourne la liste des caisses pour les rapports"""
    try:
        caisses = Caisse.objects.all().order_by('nom_association').values('id', 'nom_association', 'region')
        return JsonResponse({'caisses': list(caisses)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def export_rapport_excel_view(request, type_rapport):
    """Vue pour exporter un rapport en Excel - Accepte GET avec paramètres de requête"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    try:
        # Récupérer les paramètres de la requête (GET ou POST)
        if request.method == 'GET':
            caisse_id = request.GET.get('caisse')
            date_debut_str = request.GET.get('date_debut')
            date_fin_str = request.GET.get('date_fin')
            notes = request.GET.get('notes', '')
        else:
            # Support POST avec JSON pour compatibilité
            try:
                data = json.loads(request.body)
                caisse_id = data.get('caisse')
                date_debut_str = data.get('date_debut')
                date_fin_str = data.get('date_fin')
                notes = data.get('notes', '')
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': 'Données JSON invalides'}, status=400)
        
        # Convertir les dates
        date_debut = None
        date_fin = None
        if date_debut_str:
            try:
                date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if date_fin_str:
            try:
                date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Récupérer la caisse si spécifiée
        caisse = None
        if caisse_id:
            try:
                caisse = Caisse.objects.get(pk=caisse_id)
            except Caisse.DoesNotExist:
                pass
        
        # Créer un rapport temporaire pour l'export
        rapport = RapportActivite(
            type_rapport=type_rapport,
            caisse=caisse,
            date_debut=date_debut,
            date_fin=date_fin,
            notes=notes,
            statut='EN_ATTENTE',
            genere_par=request.user
        )
        
        # Générer les données du rapport selon le type
        if type_rapport == 'general':
            rapport.donnees = generer_rapport_general_global(date_debut, date_fin)
        elif type_rapport == 'financier':
            rapport.donnees = generer_rapport_financier_global(date_debut, date_fin)
        elif type_rapport == 'prets':
            rapport.donnees = generer_rapport_prets_global(date_debut, date_fin)
        elif type_rapport == 'membres':
            rapport.donnees = generer_rapport_membres_global(date_debut, date_fin)
        elif type_rapport == 'caisses':
            # Générer les données des caisses
            from django.db.models import Sum, Count, Q
            caisses = Caisse.objects.filter(statut='ACTIVE').annotate(
                total_membres=Count('membres'),
                total_prets=Count('prets'),
                total_montant_prets=Sum('prets__montant_accord'),
                total_montant_rembourse=Sum('prets__montant_rembourse')
            ).order_by('nom_association')
            rapport.donnees = {
                'caisses': [
                    {
                        'nom': c.nom_association,
                        'code': c.code,
                        'membres': c.total_membres,
                        'prets': c.total_prets,
                        'montant_prets': float(c.total_montant_prets or 0),
                        'montant_rembourse': float(c.total_montant_rembourse or 0),
                    }
                    for c in caisses
                ]
            }
        elif type_rapport == 'transferts':
            transferts = TransfertCaisse.objects.select_related(
                'caisse_source', 'caisse_destination'
            ).order_by('-date_transfert')
            rapport.donnees = {
                'transferts': [
                    {
                        'type': t.type_transfert,
                        'montant': float(t.montant),
                        'source': t.caisse_source.nom_association if t.caisse_source else '',
                        'destination': t.caisse_destination.nom_association if t.caisse_destination else '',
                        'statut': t.statut,
                        'date': str(t.date_transfert),
                    }
                    for t in transferts
                ]
            }
        
        # Générer l'export Excel
        response = export_rapport_excel(rapport)
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f'Erreur lors de l\'export Excel: {str(e)}', status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def export_rapport_csv_view(request, type_rapport):
    """Vue pour exporter un rapport en CSV - Accepte GET avec paramètres de requête"""
    if not request.user.is_superuser:
        return redirect('gestion_caisses:dashboard')
    
    try:
        # Récupérer les paramètres de la requête (GET ou POST)
        if request.method == 'GET':
            caisse_id = request.GET.get('caisse')
            date_debut_str = request.GET.get('date_debut')
            date_fin_str = request.GET.get('date_fin')
            notes = request.GET.get('notes', '')
        else:
            # Support POST avec JSON pour compatibilité
            try:
                data = json.loads(request.body)
                caisse_id = data.get('caisse')
                date_debut_str = data.get('date_debut')
                date_fin_str = data.get('date_fin')
                notes = data.get('notes', '')
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': 'Données JSON invalides'}, status=400)
        
        # Convertir les dates
        date_debut = None
        date_fin = None
        if date_debut_str:
            try:
                date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if date_fin_str:
            try:
                date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Récupérer la caisse si spécifiée
        caisse = None
        if caisse_id:
            try:
                caisse = Caisse.objects.get(pk=caisse_id)
            except Caisse.DoesNotExist:
                pass
        
        # Créer un rapport temporaire pour l'export
        rapport = RapportActivite(
            type_rapport=type_rapport,
            caisse=caisse,
            date_debut=date_debut,
            date_fin=date_fin,
            notes=notes,
            statut='EN_ATTENTE',
            genere_par=request.user
        )
        
        # Générer les données du rapport selon le type
        if type_rapport == 'general':
            rapport.donnees = generer_rapport_general_global(date_debut, date_fin)
        elif type_rapport == 'financier':
            rapport.donnees = generer_rapport_financier_global(date_debut, date_fin)
        elif type_rapport == 'prets':
            rapport.donnees = generer_rapport_prets_global(date_debut, date_fin)
        elif type_rapport == 'membres':
            rapport.donnees = generer_rapport_membres_global(date_debut, date_fin)
        elif type_rapport == 'caisses':
            # Générer les données des caisses
            from django.db.models import Sum, Count, Q
            caisses = Caisse.objects.filter(statut='ACTIVE').annotate(
                total_membres=Count('membres'),
                total_prets=Count('prets'),
                total_montant_prets=Sum('prets__montant_accord'),
                total_montant_rembourse=Sum('prets__montant_rembourse')
            ).order_by('nom_association')
            rapport.donnees = {
                'caisses': [
                    {
                        'nom': c.nom_association,
                        'code': c.code,
                        'membres': c.total_membres,
                        'prets': c.total_prets,
                        'montant_prets': float(c.total_montant_prets or 0),
                        'montant_rembourse': float(c.total_montant_rembourse or 0),
                    }
                    for c in caisses
                ]
            }
        elif type_rapport == 'transferts':
            transferts = TransfertCaisse.objects.select_related(
                'caisse_source', 'caisse_destination'
            ).order_by('-date_transfert')
            rapport.donnees = {
                'transferts': [
                    {
                        'type': t.type_transfert,
                        'montant': float(t.montant),
                        'source': t.caisse_source.nom_association if t.caisse_source else '',
                        'destination': t.caisse_destination.nom_association if t.caisse_destination else '',
                        'statut': t.statut,
                        'date': str(t.date_transfert),
                    }
                    for t in transferts
                ]
            }
        
        # Générer l'export CSV
        response = export_rapport_csv(rapport)
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f'Erreur lors de l\'export CSV: {str(e)}', status=500)

# API: Gestion des dépenses
class DepenseViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des dépenses des caisses"""
    serializer_class = DepenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['caisse']
    search_fields = ['Objectifdepense', 'observation', 'caisse__nom_association']
    ordering_fields = ['datedepense', 'montantdepense', 'date_creation']
    ordering = ['-datedepense', '-date_creation']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Depense.objects.all()
        # Pour les utilisateurs non admin: afficher les dépenses de leurs caisses
        user_caisses = get_user_caisses(user)
        if user_caisses.exists():
            return Depense.objects.filter(caisse__in=user_caisses)
        return Depense.objects.none()

    def perform_create(self, serializer):
        # Récupérer la caisse et le montant avant de sauvegarder
        caisse = serializer.validated_data.get('caisse')
        caisse_id = serializer.validated_data.get('caisse_id')
        if not caisse and caisse_id:
            try:
                caisse = Caisse.objects.get(pk=caisse_id)
                serializer.validated_data['caisse'] = caisse
            except Caisse.DoesNotExist:
                raise ValidationError({'caisse_id': "Caisse introuvable."})
        montant = serializer.validated_data.get('montantdepense', 0)

        if not caisse:
            raise ValidationError({'caisse': "La caisse est obligatoire pour enregistrer une dépense."})

        # Vérifier qu'il existe un exercice en cours pour cette caisse
        ensure_caisse_has_active_exercice(caisse)

        # Vérifier que le fond_disponible est suffisant
        if montant and montant > 0:
            fond_disponible = caisse.fond_disponible or 0
            if montant > fond_disponible:
                raise ValidationError({
                    'montantdepense': f'Le montant de la dépense ({montant} FCFA) dépasse le fond disponible de la caisse ({fond_disponible} FCFA).'
                })

        # Sauvegarder la dépense
        depense = serializer.save(utilisateur=self.request.user)

        # Diminuer le fond_disponible de la caisse
        if montant and montant > 0:
            caisse.fond_disponible = (caisse.fond_disponible or 0) - montant
            caisse.save(update_fields=['fond_disponible'])

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver_depense(self, request, pk=None):
        """Approuver une dépense"""
        depense = self.get_object()
        notes = request.data.get('notes', '')

        # Vérifier qu'il existe toujours un exercice en cours pour la caisse
        ensure_caisse_has_active_exercice(depense.caisse)
        
        if depense.statut != 'EN_COURS':
            return Response(
                {'error': 'Seules les dépenses en cours peuvent être approuvées'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validation de solde au moment de l'approbation
        try:
            if depense.caisse.solde_disponible_depenses < depense.montantdepense:
                return Response(
                    {'error': 'Solde insuffisant pour approuver cette dépense'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception:
            pass
        
        depense.statut = 'APPROUVEE'
        depense.approuve_par = request.user.profil_membre if hasattr(request.user, 'profil_membre') else None
        depense.notes_approbation = notes
        depense.save()
        
        serializer = self.get_serializer(depense)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter_depense(self, request, pk=None):
        """Rejeter une dépense"""
        depense = self.get_object()
        notes = request.data.get('notes', '')

        # Vérifier qu'il existe toujours un exercice en cours pour la caisse
        ensure_caisse_has_active_exercice(depense.caisse)
        
        if depense.statut != 'EN_COURS':
            return Response(
                {'error': 'Seules les dépenses en cours peuvent être rejetées'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        depense.statut = 'REJETEE'
        depense.notes_approbation = notes
        depense.save()
        
        serializer = self.get_serializer(depense)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def depense_stats(self, request):
        """Statistiques des dépenses pour une caisse"""
        # Supporter à la fois ?caisse_id= et ?caisse=
        caisse_id = request.query_params.get('caisse_id') or request.query_params.get('caisse')
        # Fallback: déduire la caisse de l'utilisateur connecté si non fourni
        if not caisse_id:
            user_caisse = get_user_caisse(request.user)
            if not user_caisse:
                raise ValidationError({'caisse_id': "Paramètre requis. Utilisez 'caisse_id' ou 'caisse'."})
            caisse_id = user_caisse.id
        
        qs = Depense.objects.filter(caisse_id=caisse_id)
        
        # Filtre période
        debut = request.query_params.get('debut')
        fin = request.query_params.get('fin')
        if debut:
            try:
                debut_dt = datetime.strptime(debut, '%Y-%m-%d')
                qs = qs.filter(date_depense__gte=debut_dt.date())
            except Exception:
                raise ValidationError({'debut': 'Format attendu YYYY-MM-DD'})
        if fin:
            try:
                fin_dt = datetime.strptime(fin, '%Y-%m-%d')
                qs = qs.filter(date_depense__lte=fin_dt.date())
            except Exception:
                raise ValidationError({'fin': 'Format attendu YYYY-MM-DD'})
        
        # Totaux par catégorie et statut
        stats = qs.aggregate(
            total_depenses=Sum('montantdepense') or 0,
            nombre_depenses=Count('id')
        )
        
        # Par catégorie
        par_categorie = []
        
        # Calcul du solde disponible des dépenses basé sur les cotisations
        try:
            caisse_obj = Caisse.objects.get(id=caisse_id)
            solde_depense = caisse_obj.solde_disponible_depenses
        except Caisse.DoesNotExist:
            raise ValidationError({'caisse_id': 'Caisse introuvable'})

        return Response({
            'caisse_id': int(caisse_id),
            'solde_disponible': solde_depense,
            'stats': stats,
            'par_categorie': par_categorie
        })


class SalaireAgentViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les salaires des agents"""
    queryset = SalaireAgent.objects.all()
    serializer_class = SalaireAgentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrer par agent, mois, année si spécifiés"""
        queryset = super().get_queryset()
        agent_id = self.request.query_params.get('agent_id')
        mois = self.request.query_params.get('mois')
        annee = self.request.query_params.get('annee')
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)
        if mois:
            queryset = queryset.filter(mois=mois)
        if annee:
            queryset = queryset.filter(annee=annee)
        return queryset
    
    @action(detail=True, methods=['post'], url_path='calculer-bonus')
    def calculer_bonus(self, request, pk=None):
        """Calcule le bonus basé sur les nouvelles caisses créées"""
        salaire = self.get_object()
        montant_par_caisse = request.data.get('montant_par_caisse', 5000)
        
        try:
            bonus = salaire.calculer_bonus_caisses(montant_par_caisse)
            serializer = self.get_serializer(salaire)
            return Response({
                'message': f'Bonus calculé: {bonus} FCFA pour {salaire.nombre_nouvelles_caisses} caisses',
                'salaire': serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Erreur lors du calcul du bonus: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='marquer-paye')
    def marquer_paye(self, request, pk=None):
        """Marque le salaire comme payé"""
        salaire = self.get_object()
        mode_paiement = request.data.get('mode_paiement', '')
        
        if salaire.statut == 'PAYE':
            return Response(
                {'error': 'Ce salaire est déjà marqué comme payé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        salaire.statut = 'PAYE'
        salaire.date_paiement = timezone.now()
        salaire.mode_paiement = mode_paiement
        salaire.save()
        
        serializer = self.get_serializer(salaire)
        return Response({
            'message': 'Salaire marqué comme payé',
            'salaire': serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='stats-mensuelles')
    def stats_mensuelles(self, request):
        """Statistiques mensuelles des salaires"""
        mois = request.query_params.get('mois')
        annee = request.query_params.get('annee')
        
        if not mois or not annee:
            # Utiliser le mois et l'année actuels par défaut
            now = timezone.now()
            mois = mois or now.month
            annee = annee or now.year
        
        try:
            mois = int(mois)
            annee = int(annee)
        except ValueError:
            return Response(
                {'error': 'Mois et année doivent être des nombres'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        salaires = SalaireAgent.objects.filter(mois=mois, annee=annee)
        
        stats = {
            'mois': mois,
            'annee': annee,
            'total_salaires_bruts': salaires.aggregate(total=Sum('total_brut'))['total'] or 0,
            'total_bonus_caisses': salaires.aggregate(total=Sum('bonus_caisses'))['total'] or 0,
            'total_primes_performance': salaires.aggregate(total=Sum('prime_performance'))['total'] or 0,
            'total_deductions': salaires.aggregate(total=Sum('deductions'))['total'] or 0,
            'total_net': salaires.aggregate(total=Sum('total_net'))['total'] or 0,
            'nombre_agents': salaires.count(),
            'nombre_payes': salaires.filter(statut='PAYE').count(),
            'nombre_en_attente': salaires.filter(statut='EN_ATTENTE').count()
        }
        
        return Response(stats)


class FichePaieViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les fiches de paie des agents"""
    queryset = FichePaie.objects.all()
    serializer_class = FichePaieSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrer par agent et période si spécifiés"""
        queryset = super().get_queryset().select_related('salaire', 'salaire__agent')
        agent_id = self.request.query_params.get('agent_id')
        mois = self.request.query_params.get('mois')
        annee = self.request.query_params.get('annee')
        salaire_id = self.request.query_params.get('salaire')
        
        if agent_id:
            queryset = queryset.filter(salaire__agent_id=agent_id)
        if mois:
            queryset = queryset.filter(mois=mois)
        if annee:
            queryset = queryset.filter(annee=annee)
        if salaire_id:
            queryset = queryset.filter(salaire_id=salaire_id)
        
        return queryset.order_by('-annee', '-mois', 'nom_agent')
    
    @action(detail=True, methods=['post'], url_path='generer-pdf')
    def generer_pdf(self, request, pk=None):
        """Génère le PDF de la fiche de paie"""
        fiche_paie = self.get_object()
        
        try:
            success = fiche_paie.generer_pdf(request.user)
            if success:
                serializer = self.get_serializer(fiche_paie)
                return Response({
                    'message': 'PDF généré avec succès',
                    'fiche_paie': serializer.data,
                    'fichier_pdf': fiche_paie.fichier_pdf.url if fiche_paie.fichier_pdf else None
                })
            else:
                return Response(
                    {'error': 'Erreur lors de la génération du PDF'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la génération du PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='generer-mensuelle')
    def generer_mensuelle(self, request):
        """Génère les fiches de paie pour tous les agents d'un mois donné"""
        mois = request.data.get('mois')
        annee = request.data.get('annee')
        
        if not mois or not annee:
            return Response(
                {'error': 'Mois et année sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            mois = int(mois)
            annee = int(annee)
        except ValueError:
            return Response(
                {'error': 'Mois et année doivent être des nombres'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer tous les salaires du mois
        salaires = SalaireAgent.objects.filter(mois=mois, annee=annee)
        
        if not salaires.exists():
            return Response(
                {'error': f'Aucun salaire trouvé pour {mois}/{annee}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        fiches_generes = []
        erreurs = []
        
        for salaire in salaires:
            try:
                # Créer la fiche de paie si elle n'existe pas
                fiche_paie, created = FichePaie.objects.get_or_create(
                    salaire=salaire,
                    defaults={'type_fiche': 'MOIS'}
                )
                
                # Générer le PDF
                if fiche_paie.generer_pdf(request.user):
                    fiches_generes.append(fiche_paie.id)
                else:
                    erreurs.append(f"Erreur lors de la génération du PDF pour {salaire.agent.nom_complet}")
                    
            except Exception as e:
                erreurs.append(f"Erreur pour {salaire.agent.nom_complet}: {str(e)}")
        
        return Response({
            'message': f'{len(fiches_generes)} fiches de paie générées avec succès',
            'fiches_generes': fiches_generes,
            'erreurs': erreurs
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agents_salaires_stats(request):
    """Statistiques globales des salaires des agents"""
    try:
        # Statistiques par mois
        stats_mensuelles = []
        current_year = timezone.now().year
        
        for mois in range(1, 13):
            salaires = SalaireAgent.objects.filter(mois=mois, annee=current_year)
            if salaires.exists():
                stats_mensuelles.append({
                    'mois': mois,
                    'annee': current_year,
                    'total_brut': salaires.aggregate(total=Sum('total_brut'))['total'] or 0,
                    'total_net': salaires.aggregate(total=Sum('total_net'))['total'] or 0,
                    'nombre_agents': salaires.count(),
                    'nombre_payes': salaires.filter(statut='PAYE').count()
                })
        
        # Top des agents par bonus caisses
        top_agents_bonus = SalaireAgent.objects.filter(
            annee=current_year
        ).select_related('agent').order_by('-bonus_caisses')[:5]
        
        top_agents = []
        for salaire in top_agents_bonus:
            top_agents.append({
                'agent': salaire.agent.nom_complet,
                'matricule': salaire.agent.matricule,
                'bonus_caisses': salaire.bonus_caisses,
                'nombre_caisses': salaire.nombre_nouvelles_caisses,
                'mois': salaire.mois
            })
        
        return Response({
            'annee_courante': current_year,
            'stats_mensuelles': stats_mensuelles,
            'top_agents_bonus': top_agents,
            'total_agents': Agent.objects.filter(statut='ACTIF').count()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erreur lors du calcul des statistiques: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ExerciceCaisseViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les exercices de caisse"""
    queryset = ExerciceCaisse.objects.all()
    serializer_class = ExerciceCaisseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['caisse', 'statut', 'date_debut', 'date_fin']
    search_fields = ['caisse__nom_association', 'caisse__code']
    ordering_fields = ['date_debut', 'date_creation', 'date_fin']
    ordering = ['-date_debut']
    
    def get_queryset(self):
        """Filtrer par caisse si spécifiée, et selon les permissions de l'utilisateur"""
        queryset = super().get_queryset().select_related('caisse')
        
        # Filtrer selon les permissions de l'utilisateur
        if not self.request.user.is_superuser:
            user_caisses = get_user_caisses(self.request.user)
            if user_caisses.exists():
                queryset = queryset.filter(caisse__in=user_caisses)
            else:
                queryset = queryset.none()
        
        # Appliquer le filtre de caisse spécifique si fourni
        caisse_id = self.request.query_params.get('caisse')
        if caisse_id:
            queryset = queryset.filter(caisse_id=caisse_id)
            
        return queryset

    @action(detail=True, methods=['get'], url_path='partage-preview')
    def partage_preview(self, request, pk=None):
        """Prévisualisation du partage de fonds proportionnel aux cotisations (hors fondation) avec intérêt.
        
        Query params:
        - taux: pourcentage d'intérêt (ex: 10 pour 10%)
        """
        from decimal import Decimal, ROUND_HALF_UP
        try:
            exercice = self.get_object()
        except Exception:
            return Response({'detail': 'Exercice introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Autorisation: non-admins ne peuvent voir que leur caisse
        if not request.user.is_superuser:
            user_caisse = get_user_caisse(request.user)
            if (not user_caisse) or (exercice.caisse_id != user_caisse.id):
                return Response({'detail': "Accès refusé à cet exercice."}, status=status.HTTP_403_FORBIDDEN)

        # Taux d'intérêt optionnel (permet de surcharger le calcul automatique si fourni)
        taux_decimal = None
        taux_str = request.query_params.get('taux')
        if taux_str not in (None, ''):
            try:
                taux_decimal = Decimal(str(taux_str)).quantize(Decimal('0.01')) / Decimal('100')
                if taux_decimal < 0:
                    return Response({'detail': 'Le taux doit être positif.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                return Response({'detail': 'Paramètre taux invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        # Période de l'exercice
        date_debut = exercice.date_debut
        date_fin = exercice.date_fin or timezone.now().date()

        # Agréger les cotisations de l'exercice (hors frais de fondation)
        # Date de référence: date de séance si disponible, sinon date d'enregistrement de la cotisation
        cotisations_qs = (
            Cotisation.objects
            .filter(caisse=exercice.caisse)
            .annotate(
                date_effective=Case(
                    When(seance__date_seance__isnull=False, then=F('seance__date_seance')),
                    default=TruncDate('date_cotisation')
                )
            )
            .filter(date_effective__gte=date_debut, date_effective__lte=date_fin)
            .select_related('membre', 'seance')
            .values('membre_id', 'membre__nom', 'membre__prenoms')
            .annotate(
                s_tempon=Sum('prix_tempon'),
                s_solidarite=Sum('frais_solidarite'),
                s_penalite=Sum('penalite_emprunt_retard'),
                s_fondation=Sum('frais_fondation'),
            )
            .order_by('membre_id')
        )

        # Récupérer les prêts non remboursés par membre
        # Un prêt est considéré non remboursé s'il est EN_COURS, EN_RETARD ou BLOQUE
        prets_non_rembourses_qs = (
            Pret.objects
            .filter(
                caisse=exercice.caisse,
                statut__in=['EN_COURS', 'EN_RETARD', 'BLOQUE']
            )
            .select_related('membre')
        )
        
        # Calculer le montant restant pour chaque prêt et grouper par membre
        prets_restants_par_membre = {}
        for pret in prets_non_rembourses_qs:
            membre_id = pret.membre_id
            # Utiliser la propriété montant_restant qui calcule correctement le reste à payer
            montant_restant = pret.montant_restant or Decimal('0')
            if membre_id not in prets_restants_par_membre:
                prets_restants_par_membre[membre_id] = Decimal('0')
            prets_restants_par_membre[membre_id] += montant_restant
        
        # Calcul du principal par membre (hors fondation)
        # Le principal est réduit du montant des prêts non remboursés
        repartition = []
        total_base = Decimal('0')
        for row in cotisations_qs:
            membre_id = row['membre_id']
            base = (row['s_tempon'] or 0) + (row['s_solidarite'] or 0) + (row['s_penalite'] or 0)
            base = Decimal(str(base))
            
            # Déduire le montant des prêts non remboursés du principal
            pret_restant = prets_restants_par_membre.get(membre_id, Decimal('0'))
            base_apres_deduction = max(base - pret_restant, Decimal('0'))
            
            # Inclure tous les membres même si leur principal est 0
            total_base += base_apres_deduction
            membre_nom = f"{row.get('membre__nom','') or ''} {(row.get('membre__prenoms','') or '')}".strip()
            if not membre_nom:
                membre_nom = f"Membre {membre_id}"
            repartition.append({
                'membre_id': membre_id,
                'membre_nom': membre_nom,
                'principal': base_apres_deduction,
                'pret_restant': str(pret_restant),  # Pour information dans la réponse
                'principal_avant_deduction': str(base)  # Pour information
            })

        total_base = total_base.quantize(Decimal('0.01'))

        # Montant total des intérêts: calculé à partir des prêts octroyés pendant l'exercice
        interet_total = Decimal('0.00')
        prets_qs = Pret.objects.filter(
            caisse=exercice.caisse
        ).filter(
            Q(date_decaissement__date__gte=date_debut, date_decaissement__date__lte=date_fin) |
            Q(date_decaissement__isnull=True, date_demande__date__gte=date_debut, date_demande__date__lte=date_fin)
        )
        for pret in prets_qs:
            interet_calcule = pret.montant_interet_calcule or Decimal('0.00')
            if not isinstance(interet_calcule, Decimal):
                try:
                    interet_calcule = Decimal(str(interet_calcule))
                except Exception:
                    interet_calcule = Decimal('0.00')
            interet_total += interet_calcule
        interet_total = interet_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Si un taux explicite est fourni, il a priorité
        if taux_decimal is not None and total_base > 0:
            interet_total = (total_base * taux_decimal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Calculer le taux effectif (pour information)
        taux_effectif = Decimal('0.00')
        if total_base > 0:
            taux_effectif = (interet_total / total_base * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Répartition proportionnelle de l'intérêt
        results = []
        for item in repartition:
            principal = Decimal(str(item['principal'] or 0)).quantize(Decimal('0.01'))
            if total_base > 0:
                interet = (principal / total_base * interet_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                interet = Decimal('0.00')
            total = (principal + interet).quantize(Decimal('0.01'))
            results.append({
                'membre_id': item['membre_id'],
                'membre_nom': item['membre_nom'],
                'principal': str(principal),
                'interet': str(interet),
                'total': str(total),
                'pret_restant': item.get('pret_restant', '0'),  # Montant du prêt non remboursé
                'principal_avant_deduction': item.get('principal_avant_deduction', str(principal)),  # Principal avant déduction du prêt
            })

        payload = {
            'exercice': {
                'id': exercice.id,
                'caisse_id': exercice.caisse_id,
                'caisse_nom': exercice.caisse.nom_association,
                'date_debut': str(date_debut),
                'date_fin': str(date_fin),
                'statut': exercice.statut,
            },
            'taux': float(taux_effectif),
            'total_base': str(total_base),
            'interet_total': str(interet_total),
            'repartition': results,
        }
        return Response(payload)

    @action(detail=True, methods=['get'], url_path='partage-pdf')
    def partage_pdf(self, request, pk=None):
        """Télécharger le PDF récapitulatif du partage de fonds."""
        exercice = self.get_object()
        # Interdire la génération de PDF si l'exercice n'est pas clôturé
        if getattr(exercice, 'statut', None) != 'CLOTURE':
            return Response(
                {'detail': "Impossible de générer le PDF: l'exercice est en cours ou non clôturé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        preview_response = self.partage_preview(request, pk=pk)
        if preview_response.status_code != status.HTTP_200_OK:
            return preview_response

        pdf_bytes = generate_partage_fonds_pdf(exercice, preview_response.data)

        filename = f"partage_fonds_{exercice.caisse.code}_{exercice.date_debut.strftime('%Y%m%d')}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser], url_path='effectuer-partage')
    def effectuer_partage(self, request, pk=None):
        """
        Effectue le partage des fonds et réinitialise les comptes de la caisse à 0,
        sauf les frais de fondation qui sont conservés dans le fond_disponible.
        """
        from decimal import Decimal
        from django.db.models import Sum, Case, When, F
        from django.db.models.functions import TruncDate
        from .models import Cotisation, AuditLog
        
        try:
            exercice = self.get_object()
        except Exception:
            return Response({'detail': 'Exercice introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Vérifier que l'exercice est clôturé
        if exercice.statut != 'CLOTURE':
            return Response(
                {'detail': "L'exercice doit être clôturé avant d'effectuer le partage."},
                status=status.HTTP_400_BAD_REQUEST
            )

        caisse = exercice.caisse
        date_debut = exercice.date_debut
        date_fin = exercice.date_fin or timezone.now().date()

        # Sauvegarder les valeurs avant modification pour l'audit
        fond_initial_avant = caisse.fond_initial
        fond_disponible_avant = caisse.fond_disponible

        # Calculer le total des frais de fondation de l'exercice
        total_frais_fondation = (
            Cotisation.objects
            .filter(caisse=caisse)
            .annotate(
                date_effective=Case(
                    When(seance__date_seance__isnull=False, then=F('seance__date_seance')),
                    default=TruncDate('date_cotisation')
                )
            )
            .filter(date_effective__gte=date_debut, date_effective__lte=date_fin)
            .aggregate(total=Sum('frais_fondation'))['total'] or Decimal('0')
        )

        # Réinitialiser les comptes de la caisse
        # fond_initial = 0
        # fond_disponible = total des frais de fondation (conservés)
        caisse.fond_initial = Decimal('0')
        caisse.fond_disponible = total_frais_fondation
        caisse.save(update_fields=['fond_initial', 'fond_disponible'])

        # Mettre à jour la CaisseGenerale si elle existe
        try:
            caisse_generale = CaisseGenerale.get_instance()
            caisse_generale.recalculer_total_caisses()
        except Exception as e:
            # Ne pas bloquer si la caisse générale n'existe pas ou erreur
            pass

        # Enregistrer dans l'audit log
        AuditLog.objects.create(
            utilisateur=request.user,
            action='MODIFICATION',
            modele='Caisse',
            objet_id=caisse.id,
            details={
                'caisse': caisse.nom_association,
                'action': 'Réinitialisation après partage',
                'fond_initial_avant': str(fond_initial_avant),
                'fond_disponible_avant': str(fond_disponible_avant),
                'fond_initial_apres': '0',
                'fond_disponible_apres': str(total_frais_fondation),
                'frais_fondation_conserves': str(total_frais_fondation),
                'exercice_id': exercice.id
            },
            ip_adresse=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'detail': 'Partage effectué avec succès. Les comptes ont été réinitialisés.',
            'caisse': {
                'id': caisse.id,
                'nom': caisse.nom_association,
                'fond_initial': str(caisse.fond_initial),
                'fond_disponible': str(caisse.fond_disponible),
                'frais_fondation_conserves': str(total_frais_fondation)
            }
        })