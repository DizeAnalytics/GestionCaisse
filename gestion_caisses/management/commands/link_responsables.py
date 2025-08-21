from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from gestion_caisses.models import Caisse, Membre


class Command(BaseCommand):
    help = "Lie (ou crée) les comptes présidente/secrétaire/trésorière à une caisse donnée, et met à jour la caisse."

    def add_arguments(self, parser):
        parser.add_argument('--caisse-id', type=int, help='ID de la caisse cible')
        parser.add_argument('--caisse-code', type=str, help='Code de la caisse cible')
        parser.add_argument('--presidente', type=str, default='presidente', help="Nom d'utilisateur pour la Présidente")
        parser.add_argument('--secretaire', type=str, default='secretaire', help="Nom d'utilisateur pour la Secrétaire")
        parser.add_argument('--tresoriere', type=str, default='tresoriere', help="Nom d'utilisateur pour la Trésorière")

    def handle(self, *args, **options):
        caisse = None
        caisse_id = options.get('caisse_id')
        caisse_code = options.get('caisse_code')

        if caisse_id:
            try:
                caisse = Caisse.objects.get(id=caisse_id)
            except Caisse.DoesNotExist:
                raise CommandError(f"Aucune caisse avec id={caisse_id}")
        elif caisse_code:
            try:
                caisse = Caisse.objects.get(code=caisse_code)
            except Caisse.DoesNotExist:
                raise CommandError(f"Aucune caisse avec code={caisse_code}")
        else:
            # Si non précisé: choisir la dernière caisse créée
            caisse = Caisse.objects.order_by('-id').first()
            if not caisse:
                raise CommandError("Aucune caisse trouvée. Créez une caisse d'abord dans l'admin.")

        self.stdout.write(self.style.WARNING(f"Caisse cible: #{caisse.id} {caisse.code} - {caisse.nom_association}"))

        roles = [
            ('PRESIDENTE', options['presidente'], 'Présidente'),
            ('SECRETAIRE', options['secretaire'], 'Secrétaire'),
            ('TRESORIERE', options['tresoriere'], 'Trésorière'),
        ]

        for role_code, username, human in roles:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': human,
                    'last_name': caisse.nom_association[:20],
                    'email': f'{username}@local.test',
                    'is_staff': False,
                }
            )
            if created:
                # Définir un mot de passe par défaut raisonné
                default_pwd = f"{username}123"
                user.set_password(default_pwd)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Utilisateur créé: {username} / {default_pwd}"))
            else:
                self.stdout.write(f"Utilisateur existant: {username}")

            # Créer ou mettre à jour le profil Membre lié
            membre = getattr(user, 'profil_membre', None)
            if not membre:
                # Générer un numéro de carte unique
                numero = f"CARD-{role_code}-{caisse.id}-{user.id}"
                membre = Membre.objects.create(
                    numero_carte_electeur=numero,
                    nom=human,
                    prenoms=user.last_name or 'Responsable',
                    date_naissance=timezone.now().date().replace(year=1990),
                    adresse='-',
                    numero_telephone='-',
                    role=role_code,
                    statut='ACTIF',
                    caisse=caisse,
                    utilisateur=user,
                )
                self.stdout.write(self.style.SUCCESS(f"Membre créé pour {username} (rôle {human})"))
            else:
                # S'assurer de la caisse et du rôle
                updated = False
                if membre.caisse_id != caisse.id:
                    membre.caisse = caisse
                    updated = True
                if membre.role != role_code:
                    membre.role = role_code
                    updated = True
                if updated:
                    membre.save()
                    self.stdout.write(self.style.SUCCESS(f"Membre mis à jour pour {username}"))
                else:
                    self.stdout.write(f"Membre déjà à jour pour {username}")

            # Renseigner la référence dirigeante dans la caisse
            if role_code == 'PRESIDENTE' and caisse.presidente_id != membre.id:
                caisse.presidente = membre
            if role_code == 'SECRETAIRE' and caisse.secretaire_id != membre.id:
                caisse.secretaire = membre
            if role_code == 'TRESORIERE' and caisse.tresoriere_id != membre.id:
                caisse.tresoriere = membre

        caisse.save()
        self.stdout.write(self.style.SUCCESS("Liaison des responsables terminée."))


