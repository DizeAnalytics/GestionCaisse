from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_caisses', '0025_exercicecaisse'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caisse',
            name='nom_association',
            field=models.CharField(max_length=200, unique=True),
        ),
    ]


