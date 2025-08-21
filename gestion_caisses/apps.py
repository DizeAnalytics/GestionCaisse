from django.apps import AppConfig


class GestionCaissesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion_caisses'
    verbose_name = 'Gestion des Caisses de Femmes'
    
    def ready(self):
        # Enregistrer les signaux sans effectuer de requêtes BD ici
        # (évite: RuntimeWarning "Accessing the database during app initialization is discouraged")
        import gestion_caisses.signals
