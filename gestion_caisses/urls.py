from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Définition du namespace de l'application
app_name = 'gestion_caisses'

# Configuration du routeur pour l'API
router = DefaultRouter()
router.register(r'regions', views.RegionViewSet)
router.register(r'prefectures', views.PrefectureViewSet)
router.register(r'communes', views.CommuneViewSet)
router.register(r'cantons', views.CantonViewSet)
router.register(r'villages', views.VillageViewSet)
router.register(r'caisses', views.CaisseViewSet)
router.register(r'membres', views.MembreViewSet)
router.register(r'prets', views.PretViewSet)
router.register(r'echeances', views.EcheanceViewSet)
router.register(r'mouvements-fonds', views.MouvementFondViewSet)
router.register(r'virements-bancaires', views.VirementBancaireViewSet)
router.register(r'caisse-generale', views.CaisseGeneraleViewSet, basename='caisse-generale')
router.register(r'caisse-generale-mouvements', views.CaisseGeneraleMouvementViewSet, basename='caisse-generale-mouvements')
router.register(r'rapports-activite', views.RapportActiviteViewSet, basename='rapports-activite')
router.register(r'audit-logs', views.AuditLogViewSet)
router.register(r'notifications', views.NotificationViewSet, basename='notifications')
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')
router.register(r'users', views.UserManagementViewSet, basename='users')

# URLs pour le frontend
urlpatterns = [
    # Page d'accueil (redirigée vers /login/)
    path('', views.index_view, name='index'),
    # Page de connexion dédiée
    path('login/', views.login_view, name='login'),
    
    # Pages du frontend après connexion
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('caisses/', views.caisses_view, name='caisses'),
    path('membres/', views.membres_view, name='membres'),
    path('prets/', views.prets_view, name='prets'),
    path('users/', views.users_view, name='users'),

    # Frontend admin personnalisé (rapports/états)
    path('admin-frontend/', views.admin_frontend_view, name='admin_frontend'),
    path('api/rapports-global/', views.rapports_global_api, name='rapports_global_api'),
    path('api/rapport-pdf/', views.admin_report_pdf, name='admin_report_pdf'),
    
    
    
    # URLs pour les agents
    path('agent/dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('agent/caisses/', views.agent_caisses_list, name='agent_caisses_list'),
    path('agent/caisse/<int:caisse_id>/', views.agent_caisse_detail, name='agent_caisse_detail'),
    path('agent/stats/api/', views.agent_stats_api, name='agent_stats_api'),
    
    # API d'authentification
    path('api/login/', views.api_login, name='api_login'),
    path('api/logout/', views.api_logout, name='api_logout'),
    # API utilitaire
    path('api/user-context/', views.user_context, name='user_context'),
    
    # API pour les rapports de caisse
    path('api/rapports-caisse/', views.rapports_caisse_api, name='rapports_caisse_api'),
    
    # URLs pour les attestations PDF
    path('attestation-pret/<int:pret_id>/pdf/', views.generate_attestation_pret_pdf, name='attestation_pret_pdf'),
    path('attestation-remboursement/<int:pret_id>/pdf/', views.generate_attestation_remboursement_pdf, name='attestation_remboursement_pdf'),
    path('guide-application.pdf', views.generate_application_guide, name='guide_application_pdf'),
    
    # API REST (inclut toutes les routes du routeur)
    path('api/', include(router.urls)),
]
