from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vagas', '0006_comite_avaliacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='vaga',
            name='avaliacao_encerrada',
            field=models.BooleanField(default=False),
        ),
    ]
