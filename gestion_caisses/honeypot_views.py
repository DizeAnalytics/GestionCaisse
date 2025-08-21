"""
Vues Honeypot pour simuler un faux panneau d'administration
"""
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json

def honeypot_admin(request):
    """Faux panneau d'administration pour piéger les attaquants"""
    if request.method == 'POST':
        # Simuler une authentification qui échoue toujours
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        # Log de la tentative d'attaque (vous pouvez l'étendre)
        print(f"🚨 Tentative d'attaque Honeypot - Username: {username}")
        
        # Toujours retourner une erreur d'authentification
        return render(request, 'gestion_caisses/honeypot_admin.html', {
            'error': 'Nom d\'utilisateur ou mot de passe incorrect.',
            'username': username
        })
    
    return render(request, 'gestion_caisses/honeypot_admin.html')

@csrf_exempt
def honeypot_api(request):
    """API Honeypot pour piéger les attaques automatisées"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '')
            password = data.get('password', '')
            
            print(f"🚨 Attaque API Honeypot - Username: {username}")
            
            # Simuler un délai pour ralentir les attaques
            import time
            time.sleep(2)
            
            return HttpResponse(json.dumps({
                'success': False,
                'message': 'Nom d\'utilisateur ou mot de passe incorrect.'
            }), content_type='application/json')
        except:
            pass
    
    return HttpResponse(json.dumps({
        'success': False,
        'message': 'Méthode non autorisée.'
    }), content_type='application/json')
