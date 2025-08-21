"""
Décorateurs pour l'audit automatique des actions utilisateur
"""
from functools import wraps
from django.http import HttpRequest
from django.contrib.auth.models import User
from .models import AuditLog
import json

def audit_action(action_type, model_name=None, get_object_id=None, get_details=None):
    """
    Décorateur pour auditer automatiquement les actions des utilisateurs
    
    Args:
        action_type (str): Type d'action (CREATION, MODIFICATION, SUPPRESSION, etc.)
        model_name (str): Nom du modèle concerné
        get_object_id (callable): Fonction pour récupérer l'ID de l'objet
        get_details (callable): Fonction pour récupérer les détails de l'action
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Exécuter la vue d'abord
            response = view_func(request, *args, **kwargs)
            
            try:
                # Récupérer l'utilisateur
                user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
                
                # Récupérer l'ID de l'objet si une fonction est fournie
                object_id = None
                if get_object_id:
                    object_id = get_object_id(request, response, *args, **kwargs)
                elif 'pk' in kwargs:
                    object_id = kwargs['pk']
                elif 'id' in kwargs:
                    object_id = kwargs['id']
                
                # Récupérer les détails si une fonction est fournie
                details = {}
                if get_details:
                    details = get_details(request, response, *args, **kwargs)
                
                # Ajouter des informations de base
                details.update({
                    'url': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'referer': request.META.get('HTTP_REFERER', ''),
                })
                
                # Créer l'entrée d'audit
                AuditLog.objects.create(
                    utilisateur=user,
                    action=action_type,
                    modele=model_name or 'Unknown',
                    objet_id=object_id or 0,
                    details=details,
                    ip_adresse=request.META.get('REMOTE_ADDR', '')
                )
                
            except Exception as e:
                # En cas d'erreur, on ne bloque pas la vue
                print(f"Erreur lors de l'audit: {e}")
            
            return response
        return wrapper
    return decorator

def audit_api_action(action_type, model_name=None):
    """
    Décorateur spécifique pour les actions API
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Exécuter la vue d'abord
            response = view_func(request, *args, **kwargs)
            
            try:
                user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
                
                # Récupérer les données de la requête
                request_data = {}
                if request.method in ['POST', 'PUT', 'PATCH']:
                    try:
                        if request.content_type == 'application/json':
                            request_data = json.loads(request.body) if request.body else {}
                        else:
                            request_data = dict(request.POST)
                    except:
                        request_data = {}
                
                # Créer l'entrée d'audit
                AuditLog.objects.create(
                    utilisateur=user,
                    action=action_type,
                    modele=model_name or 'API',
                    objet_id=kwargs.get('pk', kwargs.get('id', 0)),
                    details={
                        'url': request.path,
                        'method': request.method,
                        'request_data': request_data,
                        'response_status': response.status_code,
                        'ip_adresse': request.META.get('REMOTE_ADDR', ''),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    },
                    ip_adresse=request.META.get('REMOTE_ADDR', '')
                )
                
            except Exception as e:
                print(f"Erreur lors de l'audit API: {e}")
            
            return response
        return wrapper
    return decorator
