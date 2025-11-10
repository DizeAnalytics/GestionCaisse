"""
URL configuration for caisses_femmes project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from gestion_caisses import honeypot_views

urlpatterns = [
    # Redirection de la racine vers /gestion-caisses/login/
    path('', RedirectView.as_view(url='/gestion-caisses/login/', permanent=False), name='home'),

    # Honeypot: faux admin sur /admin/ (piège pour les attaquants)
    path('admin/', honeypot_views.honeypot_admin, name='honeypot_admin'),

    # Vrai admin déplacé sur /adminsecurelogin/
    path('adminsecurelogin/', admin.site.urls),

    # Admin également accessible sous /gestion-caisses/admin/ pour correspondre aux liens attendus
    path('gestion-caisses/admin/', admin.site.urls),

    # Application principale avec frontend
    path('gestion-caisses/', include('gestion_caisses.urls', namespace='gestion_caisses')),

    # Service Worker à la racine pour PWA (scope global)
    path('sw.js', TemplateView.as_view(template_name='pwa/sw.js', content_type='application/javascript'), name='service_worker'),
]

# Configuration des fichiers statiques et media en mode debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
