from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vagas', '0004_tor_analisado'),
    ]

    operations = [
        migrations.AddField(
            model_name='vaga',
            name='avaliacao_group_token',
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
