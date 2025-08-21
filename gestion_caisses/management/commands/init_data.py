from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from gestion_caisses.models import Region, Prefecture, Commune, Canton, Village


class Command(BaseCommand):
    help = 'Initialise la base de données avec les données de base du Togo'

    def handle(self, *args, **options):
        self.stdout.write('Initialisation de la base de données...')
        
        # Créer un super utilisateur si aucun n'existe
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@caisses-femmes.tg',
                password='admin123'
            )
            self.stdout.write(self.style.SUCCESS('Super utilisateur créé: admin/admin123'))
        
        # Créer les régions du Togo
        regions_data = [
            {'nom': 'Région des Plateaux', 'code': 'PLT'},
            {'nom': 'Région Maritime', 'code': 'MAR'},
            {'nom': 'Région Centrale', 'code': 'CEN'},
            {'nom': 'Région de la Kara', 'code': 'KAR'},
            {'nom': 'Région des Savanes', 'code': 'SAV'},
        ]
        
        for region_data in regions_data:
            region, created = Region.objects.get_or_create(
                code=region_data['code'],
                defaults=region_data
            )
            if created:
                self.stdout.write(f'Région créée: {region.nom}')
        
        # Créer quelques préfectures pour la région des Plateaux
        region_plateaux = Region.objects.get(code='PLT')
        prefectures_data = [
            {'nom': 'Préfecture d\'Ogou', 'code': 'OGO'},
            {'nom': 'Préfecture de Haho', 'code': 'HAH'},
            {'nom': 'Préfecture de Kloto', 'code': 'KLO'},
            {'nom': 'Préfecture de Wawa', 'code': 'WAW'},
            {'nom': 'Préfecture de Danyi', 'code': 'DAN'},
        ]
        
        for pref_data in prefectures_data:
            prefecture, created = Prefecture.objects.get_or_create(
                code=pref_data['code'],
                defaults={**pref_data, 'region': region_plateaux}
            )
            if created:
                self.stdout.write(f'Préfecture créée: {prefecture.nom}')
        
        # Créer quelques communes
        prefecture_ogou = Prefecture.objects.get(code='OGO')
        communes_data = [
            {'nom': 'Commune d\'Atakpamé', 'code': 'ATA'},
            {'nom': 'Commune d\'Amou', 'code': 'AMO'},
            {'nom': 'Commune d\'Ogou', 'code': 'OGO'},
        ]
        
        for com_data in communes_data:
            commune, created = Commune.objects.get_or_create(
                code=com_data['code'],
                defaults={**com_data, 'prefecture': prefecture_ogou}
            )
            if created:
                self.stdout.write(f'Commune créée: {commune.nom}')
        
        # Créer quelques cantons
        commune_atakpame = Commune.objects.get(code='ATA')
        cantons_data = [
            {'nom': 'Canton d\'Atakpamé', 'code': 'ATA'},
            {'nom': 'Canton d\'Amou', 'code': 'AMO'},
            {'nom': 'Canton d\'Ogou', 'code': 'OGO'},
        ]
        
        for can_data in cantons_data:
            canton, created = Canton.objects.get_or_create(
                code=can_data['code'],
                defaults={**can_data, 'commune': commune_atakpame}
            )
            if created:
                self.stdout.write(f'Canton créé: {canton.nom}')
        
        # Créer quelques villages
        canton_atakpame = Canton.objects.get(code='ATA')
        villages_data = [
            {'nom': 'Village d\'Atakpamé Centre', 'code': 'ATC'},
            {'nom': 'Village d\'Amou', 'code': 'AMO'},
            {'nom': 'Village d\'Ogou', 'code': 'OGO'},
        ]
        
        for vil_data in villages_data:
            village, created = Village.objects.get_or_create(
                code=vil_data['code'],
                defaults={**vil_data, 'canton': canton_atakpame}
            )
            if created:
                self.stdout.write(f'Village créé: {village.nom}')
        
        self.stdout.write(self.style.SUCCESS('Initialisation terminée avec succès!'))
        self.stdout.write('Vous pouvez maintenant vous connecter avec admin/admin123')
