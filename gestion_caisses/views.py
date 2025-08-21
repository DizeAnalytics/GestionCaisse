from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets, status, filters
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json
from django.contrib.auth.models import User
from .models import (
    Region, Prefecture, Commune, Canton, Village,
    Caisse, Membre, Pret, Echeance, MouvementFond, 
    VirementBancaire, AuditLog, Notification, Agent, CaisseGenerale, CaisseGeneraleMouvement, RapportActivite
)
from .serializers import (
    RegionSerializer, PrefectureSerializer, CommuneSerializer, CantonSerializer, VillageSerializer,
    CaisseSerializer, CaisseListSerializer, CaisseStatsSerializer,
    MembreSerializer, MembreListSerializer,
    PretSerializer, PretListSerializer,
    EcheanceSerializer, MouvementFondSerializer, VirementBancaireSerializer,
    AuditLogSerializer, NotificationSerializer, NotificationListSerializer, DashboardStatsSerializer,
    UserSerializer, CaisseGeneraleSerializer, CaisseGeneraleMouvementSerializer, RapportActiviteSerializer
)
from .services import PretService, NotificationService
from .utils import generate_pret_octroi_pdf, generate_remboursement_pdf, generate_remboursement_complet_pdf, generate_membres_liste_pdf, generate_membre_individual_pdf, get_parametres_application, generate_application_guide_pdf
from datetime import date
from .permissions import AgentPermissions


def get_user_caisse(user):
    """Retourne la caisse liée au profil de l'utilisateur (None si non liée)."""
    profil = getattr(user, 'profil_membre', None)
    return getattr(profil, 'caisse', None) if profil else None

# Contexte utilisateur pour le frontend
@login_required
def user_context(request):
    """Retourne la caisse et le rôle de l'utilisateur connecté"""
    profil = getattr(request.user, 'profil_membre', None)
    caisse_id = profil.caisse_id if profil else None
    caisse_code = profil.caisse.code if profil and profil.caisse else None
    return JsonResponse({
        'user': {
            'id': request.user.id,
            'username': request.user.username,
            'role': get_user_role(request.user),
        },
        'caisse_id': caisse_id,
        'caisse_code': caisse_code,
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
    
    # Pour tous les autres utilisateurs (présidente, secrétaire, trésorière, membres)
    # rester dans le frontend
    user_caisse = get_user_caisse(request.user)
    
    # Récupérer les paramètres de l'application pour l'affichage
    parametres = get_parametres_application()
    
    context = {
        'user': request.user,
        'user_role': get_user_role(request.user),
        'caisse_nom': user_caisse.nom_association if user_caisse else '',
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
    """Détermine le rôle de l'utilisateur basé sur son profil membre"""
    if user.is_superuser:
        return 'Administrateur'
    
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


class CaisseViewSet(viewsets.ModelViewSet):
    """Vue pour la gestion des caisses"""
    queryset = Caisse.objects.select_related(
        'region', 'prefecture', 'commune', 'canton', 'village'
    ).prefetch_related('membres').all()
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
        # Les non-admins ne voient que leur propre caisse
        if not self.request.user.is_superuser:
            caisse = get_user_caisse(self.request.user)
            if caisse:
                qs = qs.filter(id=caisse.id)
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
        # Restreindre les non-admins à leur caisse
        if not self.request.user.is_superuser:
            caisse = get_user_caisse(self.request.user)
            if caisse:
                qs = qs.filter(caisse=caisse)
            else:
                qs = qs.none()
        return qs
    
    def perform_create(self, serializer):
        # Vérifier les restrictions sur les rôles
        role = serializer.validated_data.get('role', 'MEMBRE')
        
        # Seuls les administrateurs peuvent créer des membres clés (président, secrétaire, trésorier)
        if role in ['PRESIDENTE', 'SECRETAIRE', 'TRESORIERE'] and not self.request.user.is_superuser:
            raise ValidationError({'detail': 'Seuls les administrateurs peuvent créer des présidents, secrétaires et trésoriers.'})
        
        # Forcer la caisse du user pour les non-admins
        if not self.request.user.is_superuser:
            caisse = get_user_caisse(self.request.user)
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
            caisse = get_user_caisse(self.request.user)
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
        # Restreindre les non-admins à leur caisse
        if not self.request.user.is_superuser:
            caisse = get_user_caisse(self.request.user)
            if caisse:
                qs = qs.filter(caisse=caisse)
            else:
                qs = qs.none()
        return qs
    
    def perform_create(self, serializer):
        # Vérifier que le membre n'a pas déjà un prêt en cours
        membre = serializer.validated_data.get('membre')
        if membre:
            # Vérifier s'il y a des prêts actifs (EN_COURS, EN_RETARD, BLOQUE)
            prets_actifs = Pret.objects.filter(
                membre=membre,
                statut__in=['EN_COURS', 'EN_RETARD', 'BLOQUE']
            ).exists()
            
            if prets_actifs:
                raise ValidationError({
                    'detail': f'Le membre {membre.nom_complet} a déjà un prêt en cours. Il doit d\'abord terminer le remboursement de son prêt actuel.'
                })

        # Forcer la caisse du user pour les non-admins
        if not self.request.user.is_superuser:
            caisse = get_user_caisse(self.request.user)
            pret = serializer.save(caisse=caisse)
        else:
            pret = serializer.save()

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
        
        # Générer le PDF de remboursement complet
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


class RapportActiviteViewSet(viewsets.ModelViewSet):
    queryset = RapportActivite.objects.select_related('caisse', 'genere_par').all()
    serializer_class = RapportActiviteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_rapport', 'statut', 'caisse']
    search_fields = ['notes']
    ordering_fields = ['date_generation']
    ordering = ['-date_generation']
    
    def perform_create(self, serializer):
        mouvement = serializer.save(utilisateur=self.request.user)
        
        # Mettre à jour le solde de la caisse
        caisse = mouvement.caisse
        mouvement.solde_avant = caisse.fond_disponible
        
        if mouvement.type_mouvement == 'ALIMENTATION':
            caisse.fond_disponible += mouvement.montant
        elif mouvement.type_mouvement == 'DECAISSEMENT':
            caisse.fond_disponible -= mouvement.montant
        elif mouvement.type_mouvement == 'REMBOURSEMENT':
            caisse.fond_disponible += mouvement.montant
            caisse.montant_total_remboursements += mouvement.montant
        
        caisse.save()
        mouvement.solde_apres = caisse.fond_disponible
        mouvement.save()
        
        # Log de création
        AuditLog.objects.create(
            utilisateur=self.request.user,
            action='CREATION',
            modele='MouvementFond',
            objet_id=mouvement.id,
            details={
                'type': mouvement.type_mouvement,
                'montant': str(mouvement.montant),
                'caisse': mouvement.caisse.nom_association
            },
            ip_adresse=self.request.META.get('REMOTE_ADDR')
        )


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
        """Obtenir les statistiques du tableau de bord (scopées à la caisse de l'utilisateur si non-admin)"""
        caisse_user = get_user_caisse(request.user) if not request.user.is_superuser else None
        caisse_filter = {}
        if caisse_user:
            caisse_filter = {'caisse': caisse_user}
        
        # Statistiques
        total_caisses = Caisse.objects.count() if request.user.is_superuser else 1
        total_membres = Membre.objects.filter(statut='ACTIF', **caisse_filter).count()
        # Considérer comme "actifs": tous les prêts non clôturés/annulés
        # Inclut: EN_ATTENTE, EN_ATTENTE_ADMIN, VALIDE, EN_COURS, EN_RETARD, BLOQUE
        statuts_actifs = ['EN_ATTENTE', 'EN_ATTENTE_ADMIN', 'VALIDE', 'EN_COURS', 'EN_RETARD', 'BLOQUE']
        total_prets_actifs = Pret.objects.filter(statut__in=statuts_actifs, **caisse_filter).count()
        
        # Montants financiers
        montant_total_circulation = Pret.objects.filter(statut='EN_COURS', **caisse_filter).aggregate(
            total=Sum('montant_accord')
        )['total'] or 0
        
        solde_total_disponible = (Caisse.objects.filter(id=caisse_user.id) if caisse_user else Caisse.objects.all()).aggregate(
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
            if caisse_user:
                pret_filter['caisse'] = caisse_user
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
    
    @action(detail=False, methods=['get'])
    def alertes(self, request):
        """Obtenir les alertes du système (scopées à la caisse de l'utilisateur si non-admin)"""
        caisse_user = get_user_caisse(request.user) if not request.user.is_superuser else None
        caisse_filter = {}
        if caisse_user:
            caisse_filter = {'caisse': caisse_user}
        
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
            caisses_fond_insuffisant = Caisse.objects.filter(id=caisse_user.id, fond_disponible__lt=10000) if caisse_user else Caisse.objects.none()
        
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

    # Créer un objet RapportActivite "virtuel" pour le moteur PDF
    rapport = RapportActivite()
    rapport.type_rapport = type_rapport
    rapport.caisse = caisse
    rapport.donnees = donnees

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
        caisse.solde_disponible = caisse.fond_disponible - caisse.montant_total_prets
    
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
            'solde_disponible': caisse.fond_disponible - caisse.montant_total_prets,
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
def rapports_caisse_api(request):
    """API pour les rapports de caisse"""
    try:
        # Caisse ciblée (paramètre optionnel)
        caisse_id = request.GET.get('caisse_id')
        user_caisse = get_user_caisse(request.user)
        caisse = None

        if request.user.is_superuser:
            # L'admin peut cibler n'importe quelle caisse ou défaut = première disponible
            if caisse_id:
                try:
                    caisse = Caisse.objects.get(pk=caisse_id)
                except Caisse.DoesNotExist:
                    return JsonResponse({'error': "Caisse introuvable"}, status=404)
            else:
                caisse = Caisse.objects.first()
                if not caisse:
                    return JsonResponse({'error': "Aucune caisse disponible"}, status=400)
        else:
            # Utilisateur non admin: doit être lié à une caisse
            if not user_caisse:
                return JsonResponse({'error': 'Aucune caisse associée'}, status=400)
            # Si une caisse_id est fournie, vérifier l'autorisation
            if caisse_id and str(user_caisse.id) != str(caisse_id):
                return JsonResponse({'error': "Accès non autorisé à cette caisse"}, status=403)
            caisse = user_caisse
        
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
        if type_rapport == 'general':
            rapport = generer_rapport_general_caisse(caisse, date_debut, date_fin)
        elif type_rapport == 'financier':
            rapport = generer_rapport_financier_caisse(caisse, date_debut, date_fin)
        elif type_rapport == 'prets':
            rapport = generer_rapport_prets_caisse(caisse, date_debut, date_fin)
        elif type_rapport == 'membres':
            rapport = generer_rapport_membres_caisse(caisse, date_debut, date_fin)
        elif type_rapport == 'echeances':
            rapport = generer_rapport_echeances_caisse(caisse, date_debut, date_fin)
        else:
            return JsonResponse({'error': 'Type de rapport invalide'}, status=400)
        
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


def generer_rapport_general_global(date_debut=None, date_fin=None):
    """Rapport général agrégé pour toutes les caisses, même structure que le frontend."""
    from django.db.models import Count, Sum, Avg, Q
    caisses = Caisse.objects.all()
    
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
    
    # Appliquer les filtres de date
    membres = Membre.objects.filter(filtres_date_membres)
    prets = Pret.objects.filter(filtres_date_prets)
    mouvements = MouvementFond.objects.filter(filtres_date_mouvements)

    membres_stats = {
        'total': membres.count(),
        'actifs': membres.filter(statut='ACTIF').count(),
        'inactifs': membres.filter(statut='INACTIF').count(),
        'suspendus': membres.filter(statut='SUSPENDU').count(),
        'femmes': membres.filter(sexe='F').count(),
        'hommes': membres.filter(sexe='M').count(),
    }

    prets_stats = {
        'total': prets.count(),
        'en_cours': prets.filter(statut='EN_COURS').count(),
        'rembourses': prets.filter(statut='REMBOURSE').count(),
        'en_retard': prets.filter(statut='EN_RETARD').count(),
        'montant_total': float(prets.aggregate(total=Sum('montant_accord'))['total'] or 0),
        'montant_rembourse': float(prets.aggregate(total=Sum('montant_rembourse'))['total'] or 0),
        'montant_moyen': float(prets.aggregate(moy=Avg('montant_accord'))['moy'] or 0),
    }

    mouvements_aggr = mouvements.aggregate(
        total_alimentations=Sum('montant', filter=Q(type_mouvement='ALIMENTATION')),
        total_decaissements=Sum('montant', filter=Q(type_mouvement='DECAISSEMENT')),
        total_remboursements=Sum('montant', filter=Q(type_mouvement='REMBOURSEMENT')),
        total_frais=Sum('montant', filter=Q(type_mouvement='FRAIS'))
    )

    fonds = {
        'fond_initial': float(caisses.aggregate(total=Sum('fond_initial'))['total'] or 0),
        'fond_disponible': float(caisses.aggregate(total=Sum('fond_disponible'))['total'] or 0),
        'montant_total_prets': float(caisses.aggregate(total=Sum('montant_total_prets'))['total'] or 0),
        'solde_disponible': float((caisses.aggregate(fd=Sum('fond_disponible'))['fd'] or 0) - (caisses.aggregate(mp=Sum('montant_total_prets'))['mp'] or 0)),
    }

    echeances_retard = {
        'total_echeances_retard': Echeance.objects.filter(statut='EN_RETARD').count(),
        'montant_retard': float(Echeance.objects.filter(statut='EN_RETARD').aggregate(total=Sum('montant_echeance'))['total'] or 0),
    }

    return {
        'caisse': {
            'nom': 'Toutes les caisses',
            'code': 'GLOBAL',
            'date_creation': None,
            'statut': 'AGREGE',
        },
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
    
    # Filtres de date
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_mouvement__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_mouvement__lte=date_fin)
    
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
    
    # Montants des prêts en cours et remboursés (ignorer les prêts non octroyés)
    total_prets_octroyes = caisse.prets.filter(statut='EN_COURS').aggregate(total=Sum('montant_accord'))['total'] or 0
    total_prets_rembourses = caisse.prets.filter(statut='REMBOURSE').aggregate(total=Sum('montant_accord'))['total'] or 0
    total_prets_caisse = (total_prets_octroyes or 0) + (total_prets_rembourses or 0)

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
            'solde_disponible': float((caisse.fond_disponible or 0) - (total_prets_caisse or 0)),
        },
        'prets_financiers': {
            'octroyes_total': float(total_prets_octroyes),
            'rembourses_total': float(total_prets_rembourses),
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


def generer_rapport_financier_global(date_debut=None, date_fin=None):
    """Rapport financier agrégé pour toutes les caisses."""
    from django.db.models import Sum, Q
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_mouvement__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_mouvement__lte=date_fin)

    mouvements = MouvementFond.objects.filter(filtres_date).order_by('-date_mouvement')
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

    from django.db.models import Sum as DSum
    from .models import Caisse
    # Agrégations robustes (montant_total_prets basé sur les prêts réels)
    total_fond_initial = Caisse.objects.aggregate(total=DSum('fond_initial'))['total'] or 0
    total_fond_disponible = Caisse.objects.aggregate(total=DSum('fond_disponible'))['total'] or 0
    from .models import Pret
    total_prets_octroyes = Pret.objects.filter(statut='EN_COURS').aggregate(total=DSum('montant_accord'))['total'] or 0
    total_prets_rembourses = Pret.objects.filter(statut='REMBOURSE').aggregate(total=DSum('montant_accord'))['total'] or 0
    total_prets_accordes = (total_prets_octroyes or 0) + (total_prets_rembourses or 0)

    fonds_actuels = {
        'fond_initial': float(total_fond_initial),
        'fond_disponible': float(total_fond_disponible),
        'montant_total_prets': float(total_prets_accordes),
        'solde_disponible': float((total_fond_disponible or 0) - (total_prets_accordes or 0)),
    }

    # Synthèse par caisse (pour affichage détaillé dans le PDF)
    par_caisse = []
    for c in Caisse.objects.all().order_by('nom_association'):
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
            'solde_disponible': float((c.fond_disponible or 0) - (total_prets_caisse or 0)),
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


def generer_rapport_prets_global(date_debut=None, date_fin=None):
    """Rapport des prêts agrégé pour toutes les caisses."""
    from django.db.models import Sum, Avg, Q
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_demande__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_demande__lte=date_fin)

    prets = Pret.objects.filter(filtres_date).select_related('membre', 'caisse')
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


def generer_rapport_membres_global(date_debut=None, date_fin=None):
    from django.db.models import Count, Sum, Q
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_adhesion__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_adhesion__lte=date_fin)

    membres = Membre.objects.filter(filtres_date)
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


def generer_rapport_echeances_global(date_debut=None, date_fin=None):
    from django.db.models import Sum, Q
    from django.utils import timezone
    filtres_date = Q()
    if date_debut:
        filtres_date &= Q(date_echeance__gte=date_debut)
    if date_fin:
        filtres_date &= Q(date_echeance__lte=date_fin)

    echeances = Echeance.objects.filter(filtres_date).select_related('pret', 'pret__membre', 'pret__caisse')
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
