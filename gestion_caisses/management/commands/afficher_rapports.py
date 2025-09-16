from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from gestion_caisses.models import RapportActivite
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Affiche un résumé détaillé des rapports d\'activités existants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--caisse',
            type=str,
            help='Filtrer par nom de caisse'
        )
        parser.add_argument(
            '--type',
            type=str,
            help='Filtrer par type de rapport'
        )
        parser.add_argument(
            '--statut',
            type=str,
            help='Filtrer par statut'
        )
        parser.add_argument(
            '--periode',
            type=int,
            default=30,
            help='Nombre de jours pour la période (défaut: 30)'
        )

    def handle(self, *args, **options):
        # Construire le filtre de base
        filtres = Q()
        
        if options['caisse']:
            filtres &= Q(caisse__nom_association__icontains=options['caisse'])
        
        if options['type']:
            filtres &= Q(type_rapport=options['type'])
        
        if options['statut']:
            filtres &= Q(statut=options['statut'])
        
        # Filtre par période
        date_limite = datetime.now().date() - timedelta(days=options['periode'])
        filtres &= Q(date_generation__gte=date_limite) | Q(date_generation__isnull=True)
        
        # Récupérer les rapports filtrés
        rapports = RapportActivite.objects.filter(filtres).select_related('caisse', 'genere_par')
        
        # Afficher le résumé
        self._afficher_resume_general(rapports)
        self._afficher_repartition_par_type(rapports)
        self._afficher_repartition_par_statut(rapports)
        self._afficher_repartition_par_caisse(rapports)
        self._afficher_rapports_recents(rapports)
        
        if options['caisse'] or options['type'] or options['statut']:
            self._afficher_details_rapports(rapports)

    def _afficher_resume_general(self, rapports):
        """Affiche un résumé général"""
        total = rapports.count()
        rapports_generes = rapports.filter(statut='GENERE').count()
        rapports_en_attente = rapports.filter(statut='EN_ATTENTE').count()
        rapports_echec = rapports.filter(statut='ECHEC').count()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📊 RÉSUMÉ GÉNÉRAL DES RAPPORTS D'ACTIVITÉS")
        self.stdout.write("="*60)
        self.stdout.write(f"Total des rapports: {total}")
        self.stdout.write(f"✅ Générés: {rapports_generes}")
        self.stdout.write(f"⏳ En attente: {rapports_en_attente}")
        self.stdout.write(f"❌ En échec: {rapports_echec}")
        
        if total > 0:
            taux_succes = (rapports_generes / total) * 100
            self.stdout.write(f"📈 Taux de succès: {taux_succes:.1f}%")

    def _afficher_repartition_par_type(self, rapports):
        """Affiche la répartition par type de rapport"""
        repartition = rapports.values('type_rapport').annotate(
            count=Count('id')
        ).order_by('-count')
        
        self.stdout.write("\n📋 RÉPARTITION PAR TYPE DE RAPPORT")
        self.stdout.write("-" * 40)
        
        for item in repartition:
            type_rapport = item['type_rapport']
            count = item['count']
            icone = self._get_icone_type(type_rapport)
            self.stdout.write(f"{icone} {type_rapport.title()}: {count}")

    def _afficher_repartition_par_statut(self, rapports):
        """Affiche la répartition par statut"""
        repartition = rapports.values('statut').annotate(
            count=Count('id')
        ).order_by('-count')
        
        self.stdout.write("\n🔄 RÉPARTITION PAR STATUT")
        self.stdout.write("-" * 30)
        
        for item in repartition:
            statut = item['statut']
            count = item['count']
            icone = self._get_icone_statut(statut)
            self.stdout.write(f"{icone} {statut}: {count}")

    def _afficher_repartition_par_caisse(self, rapports):
        """Affiche la répartition par caisse"""
        repartition = rapports.values('caisse__nom_association').annotate(
            count=Count('id')
        ).order_by('-count')
        
        self.stdout.write("\n🏦 RÉPARTITION PAR CAISSE")
        self.stdout.write("-" * 30)
        
        for item in repartition:
            nom_caisse = item['caisse__nom_association'] or 'Global'
            count = item['count']
            self.stdout.write(f"🏛️ {nom_caisse}: {count}")

    def _afficher_rapports_recents(self, rapports):
        """Affiche les rapports les plus récents"""
        rapports_recents = rapports.filter(
            date_generation__isnull=False
        ).order_by('-date_generation')[:10]
        
        if rapports_recents:
            self.stdout.write("\n🕒 RAPPORTS LES PLUS RÉCENTS")
            self.stdout.write("-" * 40)
            
            for rapport in rapports_recents:
                date_gen = rapport.date_generation.strftime('%d/%m/%Y %H:%M')
                type_rapport = rapport.type_rapport.title()
                nom_caisse = rapport.caisse.nom_association if rapport.caisse else 'Global'
                statut = rapport.statut
                
                self.stdout.write(
                    f"📅 {date_gen} | {type_rapport} | {nom_caisse} | {statut}"
                )

    def _afficher_details_rapports(self, rapports):
        """Affiche les détails des rapports filtrés"""
        self.stdout.write("\n📝 DÉTAILS DES RAPPORTS FILTRÉS")
        self.stdout.write("-" * 40)
        
        for rapport in rapports[:20]:  # Limiter à 20 pour éviter l'overflow
            self.stdout.write(f"\n🔍 Rapport #{rapport.id}")
            self.stdout.write(f"   Type: {rapport.type_rapport}")
            self.stdout.write(f"   Caisse: {rapport.caisse.nom_association if rapport.caisse else 'Global'}")
            self.stdout.write(f"   Statut: {rapport.statut}")
            self.stdout.write(f"   Période: {rapport.date_debut} → {rapport.date_fin}")
            
            if rapport.date_generation:
                self.stdout.write(f"   Généré le: {rapport.date_generation.strftime('%d/%m/%Y %H:%M')}")
                if rapport.genere_par:
                    self.stdout.write(f"   Par: {rapport.genere_par.username}")
            
            if rapport.notes:
                self.stdout.write(f"   Notes: {rapport.notes[:100]}...")
        
        if rapports.count() > 20:
            self.stdout.write(f"\n... et {rapports.count() - 20} autres rapports")

    def _get_icone_type(self, type_rapport):
        """Retourne l'icône appropriée pour le type de rapport"""
        icones = {
            'general': '📊',
            'financier': '💰',
            'prets': '🗓️',
            'membres': '👥',
            'echeances': '📅'
        }
        return icones.get(type_rapport, '📄')

    def _get_icone_statut(self, statut):
        """Retourne l'icône appropriée pour le statut"""
        icones = {
            'EN_ATTENTE': '⏳',
            'GENERE': '✅',
            'ECHEC': '❌'
        }
        return icones.get(statut, '❓')
