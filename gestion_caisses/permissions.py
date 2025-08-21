from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AgentPermissions:
    """Gestion des permissions pour les agents"""
    
    @staticmethod
    def is_agent(user):
        """Vérifie si l'utilisateur est un agent"""
        return hasattr(user, 'profil_agent') and user.profil_agent is not None
    
    @staticmethod
    def get_agent_caisses(user):
        """Retourne les caisses assignées à l'agent"""
        if AgentPermissions.is_agent(user):
            return user.profil_agent.caisses.all()
        return []
    
    @staticmethod
    def can_access_caisse(user, caisse):
        """Vérifie si l'agent peut accéder à une caisse spécifique"""
        if user.is_superuser:
            return True
        
        if AgentPermissions.is_agent(user):
            return caisse in user.profil_agent.caisses.all()
        
        return False
    
    @staticmethod
    def can_access_membre(user, membre):
        """Vérifie si l'agent peut accéder à un membre spécifique"""
        if user.is_superuser:
            return True
        
        if AgentPermissions.is_agent(user):
            return membre.caisse in user.profil_agent.caisses.all()
        
        return False
    
    @staticmethod
    def can_access_pret(user, pret):
        """Vérifie si l'agent peut accéder à un prêt spécifique"""
        if user.is_superuser:
            return True
        
        if AgentPermissions.is_agent(user):
            return pret.caisse in user.profil_agent.caisses.all()
        
        return False


class AgentAdminMixin:
    """Mixin pour filtrer les données selon les permissions des agents"""
    
    def get_queryset(self, request):
        """Filtre le queryset selon les permissions de l'utilisateur"""
        qs = super().get_queryset(request)
        
        # Si c'est un superuser, retourner tout
        if request.user.is_superuser:
            return qs
        
        # Si c'est un agent, filtrer selon ses caisses
        if AgentPermissions.is_agent(request.user):
            agent_caisses = AgentPermissions.get_agent_caisses(request.user)
            if hasattr(self.model, 'caisse'):
                # Pour les modèles liés à une caisse (Membre, Pret, etc.)
                return qs.filter(caisse__in=agent_caisses)
            elif self.model.__name__ == 'Caisse':
                # Pour le modèle Caisse lui-même
                return qs.filter(id__in=agent_caisses.values_list('id', flat=True))
        
        # Par défaut, retourner un queryset vide pour les autres utilisateurs
        return qs.none()
    
    def has_add_permission(self, request):
        """Seuls les superusers peuvent ajouter"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Vérifie les permissions de modification"""
        if request.user.is_superuser:
            return True
        
        if obj is None:
            # Pour la liste, vérifier si l'utilisateur a au moins une caisse
            if AgentPermissions.is_agent(request.user):
                return AgentPermissions.get_agent_caisses(request.user).exists()
            return False
        
        # Pour un objet spécifique
        if hasattr(obj, 'caisse'):
            return AgentPermissions.can_access_caisse(request.user, obj.caisse)
        elif obj.__class__.__name__ == 'Caisse':
            return AgentPermissions.can_access_caisse(request.user, obj)
        
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Seuls les superusers peuvent supprimer"""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """Vérifie les permissions de visualisation"""
        if request.user.is_superuser:
            return True
        
        if obj is None:
            # Pour la liste, vérifier si l'utilisateur a au moins une caisse
            if AgentPermissions.is_agent(request.user):
                return AgentPermissions.get_agent_caisses(request.user).exists()
            return False
        
        # Pour un objet spécifique
        if hasattr(obj, 'caisse'):
            return AgentPermissions.can_access_caisse(request.user, obj.caisse)
        elif obj.__class__.__name__ == 'Caisse':
            return AgentPermissions.can_access_caisse(request.user, obj)
        
        return False
