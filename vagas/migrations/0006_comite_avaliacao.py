import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('candidatos', '0005_respostas_perguntas'),
        ('vagas', '0005_avaliacao_group_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComiteSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('vaga', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comite_sessions', to='vagas.vaga')),
                ('avaliador_nome', models.CharField(max_length=200)),
                ('avaliador_email', models.EmailField(blank=True)),
                ('estado', models.CharField(choices=[('pendente', 'Pendente'), ('submetido', 'Submetido')], default='pendente', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='ComiteAvaliacao',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='avaliacoes', to='vagas.comitesession')),
                ('candidato', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comite_avaliacoes', to='candidatos.candidato')),
                ('pontuacao', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('recomendacao', models.CharField(blank=True, max_length=20)),
                ('pontos_fortes', models.TextField(blank=True)),
                ('pontos_fracos', models.TextField(blank=True)),
                ('notas', models.TextField(blank=True)),
                ('data_entrevista', models.DateField(blank=True, null=True)),
                ('respostas_perguntas', models.JSONField(default=list)),
            ],
            options={'unique_together': {('session', 'candidato')}},
        ),
    ]
