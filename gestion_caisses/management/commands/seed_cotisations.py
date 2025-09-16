from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from dateutil.relativedelta import relativedelta
import random

from gestion_caisses.models import Caisse, Membre, SeanceReunion, Cotisation


class Command(BaseCommand):
    help = "Génère des séances et cotisations de test pour quelques caisses et membres."

    def add_arguments(self, parser):
        parser.add_argument('--caisses', type=int, default=2, help='Nombre de caisses à peupler (par défaut 2)')
        parser.add_argument('--membres-par-caisse', type=int, default=5, help='Nombre de membres à sélectionner par caisse (par défaut 5)')
        parser.add_argument('--mois', type=int, default=4, help='Nombre de mois de cotisations à générer (par défaut 4)')

    def handle(self, *args, **options):
        nb_caisses = options['caisses']
        nb_membres = options['membres_par_caisse']
        nb_mois = options['mois']

        caisses = Caisse.objects.all()[:nb_caisses]
        if not caisses.exists():
            self.stdout.write(self.style.WARNING("Aucune caisse trouvée. Rien à faire."))
            return

        total_cotisations = 0
        today = timezone.now().date().replace(day=5)

        for caisse in caisses:
            membres = Membre.objects.filter(caisse=caisse, statut='ACTIF')[:nb_membres]
            if not membres.exists():
                self.stdout.write(self.style.WARNING(f"Aucun membre actif pour la caisse {caisse.nom_association}."))
                continue

            # Créer des séances mensuelles sur nb_mois en arrière
            seances = []
            for i in range(nb_mois):
                d = (today - relativedelta(months=i))
                seance, _ = SeanceReunion.objects.get_or_create(
                    caisse=caisse,
                    date_seance=d,
                    defaults={'titre': f'Séance {d.strftime("%Y-%m")}', 'notes': 'Généré automatiquement'}
                )
                seances.append(seance)

            # Pour chaque membre sélectionné, créer une cotisation sur chaque séance
            for membre in membres:
                for seance in seances:
                    # Montants aléatoires mais modestes
                    prix_tempon = random.choice([500, 1000, 1500])
                    frais_solidarite = random.choice([200, 300])
                    frais_fondation = random.choice([0, 100])
                    penalite = random.choice([0, 0, 100])
                    Cotisation.objects.create(
                        membre=membre,
                        caisse=caisse,
                        seance=seance,
                        prix_tempon=prix_tempon,
                        frais_solidarite=frais_solidarite,
                        frais_fondation=frais_fondation,
                        penalite_emprunt_retard=penalite,
                        description='Cotisation de test (seed)'
                    )
                    total_cotisations += 1

            self.stdout.write(self.style.SUCCESS(f"Caisse {caisse.nom_association}: {len(seances)} séance(s) et {len(membres) * len(seances)} cotisations créées."))

        self.stdout.write(self.style.SUCCESS(f"Terminé. Total cotisations créées: {total_cotisations}"))


