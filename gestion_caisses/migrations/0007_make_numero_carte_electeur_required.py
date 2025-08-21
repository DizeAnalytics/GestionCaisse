# Generated manually

from django.db import migrations, models


def generate_default_numero_carte(apps, schema_editor):
    """Génère un numéro de carte d'électeur par défaut pour les agents existants"""
    Agent = apps.get_model('gestion_caisses', 'Agent')
    
    for agent in Agent.objects.filter(numero_carte_electeur__isnull=True):
        # Générer un numéro unique basé sur le matricule
        numero_carte = f"AGENT_{agent.matricule}"
        counter = 1
        
        # S'assurer que le numéro est unique
        while Agent.objects.filter(numero_carte_electeur=numero_carte).exists():
            numero_carte = f"AGENT_{agent.matricule}_{counter}"
            counter += 1
        
        agent.numero_carte_electeur = numero_carte
        agent.save()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_caisses', '0006_add_numero_carte_electeur_to_agent'),
    ]

    operations = [
        # D'abord, générer des valeurs par défaut pour les agents existants
        migrations.RunPython(generate_default_numero_carte, reverse_code=migrations.RunPython.noop),
        
        # Ensuite, rendre le champ obligatoire
        migrations.AlterField(
            model_name='agent',
            name='numero_carte_electeur',
            field=models.CharField(
                max_length=20, 
                unique=True,
                help_text="Numéro de carte d'électeur unique de l'agent"
            ),
        ),
    ]
