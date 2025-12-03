from django.core.management.base import BaseCommand
from django.utils import timezone

from gestion_caisses.models import ExerciceCaisse


class Command(BaseCommand):
    help = (
        "Clôture automatiquement tous les exercices dont la date de fin est dépassée "
        "mais qui sont encore marqués 'EN_COURS'. "
        "À utiliser pour corriger les données existantes (ex : caisse MAWUSSE)."
    )

    def handle(self, *args, **options):
        today = timezone.now().date()
        qs = ExerciceCaisse.objects.filter(statut="EN_COURS", date_fin__lt=today)
        count = qs.count()
        qs.update(statut="CLOTURE")
        self.stdout.write(
            self.style.SUCCESS(
                f"{count} exercice(s) ont été mis à jour de 'EN_COURS' vers 'CLOTURE'."
            )
        )


