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
router.register(r'agents', views.AgentViewSet)
router.register(r'caisses', views.CaisseViewSet)
router.register(r'membres', views.MembreViewSet)
router.register(r'prets', views.PretViewSet)
router.register(r'echeances', views.EcheanceViewSet)
router.register(r'mouvements-fonds', views.MouvementFondViewSet)
router.register(r'virements-bancaires', views.VirementBancaireViewSet)
router.register(r'caisse-generale', views.CaisseGeneraleViewSet, basename='caisse-generale')
router.register(r'caisse-generale-mouvements', views.CaisseGeneraleMouvementViewSet, basename='caisse-generale-mouvements')
# router.register(r'rapports-activite', views.RapportActiviteViewSet, basename='rapports-activite')  # Supprimé
router.register(r'audit-logs', views.AuditLogViewSet)
router.register(r'notifications', views.NotificationViewSet, basename='notifications')
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')
router.register(r'users', views.UserManagementViewSet, basename='users')
router.register(r'seances', views.SeanceReunionViewSet)
router.register(r'cotisations', views.CotisationViewSet)
router.register(r'cotisations-stats', views.CotisationStatsViewSet, basename='cotisations-stats')
router.register(r'depenses', views.DepenseViewSet, basename='depenses')
router.register(r'salaires-agents', views.SalaireAgentViewSet, basename='salaires-agents')
router.register(r'fiches-paie', views.FichePaieViewSet, basename='fiches-paie')
router.register(r'exercices-caisse', views.ExerciceCaisseViewSet, basename='exercices-caisse')

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
    path('caisses-cards/', views.caisses_cards_view, name='caisses_cards'),
    path('api/rapports-global/', views.rapports_global_api, name='rapports_global_api'),
    path('api/rapport-pdf/', views.admin_report_pdf, name='admin_report_pdf'),
    
    # URLs pour les rapports et états admin
    path('admin/rapport-general/', views.rapport_general_view, name='rapport_general'),
    path('admin/rapport-financier/', views.rapport_financier_view, name='rapport_financier'),
    path('admin/rapport-prets/', views.rapport_prets_view, name='rapport_prets'),
    path('admin/rapport-membres/', views.rapport_membres_view, name='rapport_membres'),
    path('admin/rapport-caisses/', views.rapport_caisses_view, name='rapport_caisses'),
    path('admin/rapport-transferts/', views.rapport_transferts_view, name='rapport_transferts'),
    path('admin/rapport-audit/', views.rapport_audit_view, name='rapport_audit'),
    
    # URLs pour l'impression des états
    path('admin/etat-general/', views.etat_general_print_view, name='etat_general_print'),
    path('admin/etat-financier/', views.etat_financier_print_view, name='etat_financier_print'),
    path('admin/etat-prets/', views.etat_prets_print_view, name='etat_prets_print'),
    path('admin/etat-caisses/', views.etat_caisses_print_view, name='etat_caisses_print'),
    path('admin/etat-transferts/', views.etat_transferts_print_view, name='etat_transferts_print'),
    
    # URLs pour les rapports d'activité
    path('rapport/generer-pdf/', views.generer_rapport_pdf_admin, name='generer_rapport_pdf_admin'),
    path('rapport/<int:rapport_id>/telecharger/', views.telecharger_rapport_pdf, name='telecharger_rapport_pdf'),
    path('rapport/<int:rapport_id>/previsualiser/', views.previsualiser_rapport_pdf, name='previsualiser_rapport_pdf'),
    path('rapport/caisses/', views.lister_caisses_rapport, name='lister_caisses_rapport'),

    # URLs pour l'export des rapports
    path('rapport/export-excel/<str:type_rapport>/', views.export_rapport_excel_view, name='export_rapport_excel_view'),
    path('rapport/export-csv/<str:type_rapport>/', views.export_rapport_csv_view, name='export_rapport_csv_view'),
    
    # URLs pour la génération des rapports PDF depuis l'admin
    path('admin/rapport/generer-pdf/', views.generer_rapport_pdf_admin, name='generer_rapport_pdf_admin'),
    path('admin/rapport/<int:rapport_id>/telecharger-pdf/', views.telecharger_rapport_pdf, name='telecharger_rapport_pdf'),
    path('admin/rapport/<int:rapport_id>/previsualiser-pdf/', views.previsualiser_rapport_pdf, name='previsualiser_rapport_pdf'),
    path('admin/rapport/caisses/', views.lister_caisses_rapport, name='lister_caisses_rapport'),
    
    # URLs pour la maintenance du système
    path('admin/synchroniser-systeme/', views.synchroniser_systeme_view, name='synchroniser_systeme'),
    path('admin/verifier-integrite/', views.verifier_integrite_view, name='verifier_integrite'),
    path('admin/nettoyer-donnees/', views.nettoyer_donnees_view, name='nettoyer_donnees'),
    path('admin/sauvegarder-systeme/', views.sauvegarder_systeme_view, name='sauvegarder_systeme'),
    
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
    
    # API pour les salaires des agents
    path('api/agents-salaires-stats/', views.agents_salaires_stats, name='agents_salaires_stats'),
    
    # URLs pour les attestations PDF
    path('attestation-pret/<int:pret_id>/pdf/', views.generate_attestation_pret_pdf, name='attestation_pret_pdf'),
    path('attestation-remboursement/<int:pret_id>/pdf/', views.generate_attestation_remboursement_pdf, name='attestation_remboursement_pdf'),
    path('guide-application.pdf', views.generate_application_guide, name='guide_application_pdf'),
    
    # API REST (inclut toutes les routes du routeur)
    path('api/', include(router.urls)),
]
