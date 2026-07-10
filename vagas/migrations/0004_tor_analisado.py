from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vagas', '0003_tor_aprovado'),
    ]

    operations = [
        migrations.AddField(
            model_name='vaga',
            name='tor_analisado',
            field=models.BooleanField(default=False),
        ),
    ]
