from django.shortcuts import render


def ajuda_view(request):
    steps = [
        {"icon": "fa-briefcase", "title": "Criar Vaga", "desc": "Define o cargo, requisitos e competencias necessarias."},
        {"icon": "fa-file-arrow-up", "title": "Carregar CVs", "desc": "Faz upload dos CVs dos candidatos para a vaga."},
        {"icon": "fa-star", "title": "Calcular Scores", "desc": "O sistema pontua automaticamente cada candidato."},
        {"icon": "fa-list-check", "title": "Gerir Pipeline", "desc": "Move candidatos pelas etapas do processo de seleccao."},
        {"icon": "fa-file-export", "title": "Exportar", "desc": "Gera relatorios em Excel ou Word com os resultados."},
    ]

    score_dims = [
        {"name": "Experiencia", "weight": "40%", "desc": "Anos de experiencia relevante na area do cargo."},
        {"name": "Competencias", "weight": "35%", "desc": "Correspondencia entre as competencias do candidato e as exigidas pela vaga."},
        {"name": "Formacao", "weight": "25%", "desc": "Nivel academico e area de formacao em relacao aos requisitos."},
    ]

    pipeline_stages = [
        "Candidatura Recebida",
        "Triagem CV",
        "Entrevista Inicial",
        "Entrevista Tecnica",
        "Proposta Enviada",
        "Contratado",
        "Rejeitado",
    ]

    return render(request, "ajuda/ajuda.html", {
        "steps": steps,
        "score_dims": score_dims,
        "pipeline_stages": pipeline_stages,
    })
