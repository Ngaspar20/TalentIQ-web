from django.shortcuts import render


def ajuda_view(request):
    steps = [
        {"num": 1, "icon": "fa-briefcase", "title": "Criar Vaga", "desc": "Carregue o ToR ou preencha o formulÃ¡rio. A IA extrai os requisitos.", "bg": "#eff6ff", "color": "#1d4ed8"},
        {"num": 2, "icon": "fa-file-arrow-up", "title": "Carregar CVs", "desc": "FaÃ§a upload dos CVs dos candidatos e associe-os Ã  vaga.", "bg": "#f5f3ff", "color": "#8b5cf6"},
        {"num": 3, "icon": "fa-chart-bar", "title": "Calcular Scores", "desc": "A IA puntua cada candidato em 3 dimensÃµes (0â€“100).", "bg": "#f0fdf4", "color": "#10b981"},
        {"num": 4, "icon": "fa-filter", "title": "Gerir Pipeline", "desc": "Mova candidatos pelas etapas e exporte os relatÃ³rios.", "bg": "#fffbeb", "color": "#f59e0b"},
    ]
    vaga_fields = [
        {"name": "TÃ­tulo", "desc": "nome do cargo", "color": "#1d4ed8", "important": False},
        {"name": "CompetÃªncias", "desc": "lista separada por vÃ­rgula", "color": "#1d4ed8", "important": True},
        {"name": "FormaÃ§Ã£o MÃ­nima", "desc": "licenciatura, mestradoâ€¦", "color": "#1d4ed8", "important": True},
        {"name": "ExperiÃªncia MÃ­n.", "desc": "nÃºmero de anos", "color": "#1d4ed8", "important": True},
        {"name": "Responsabilidades", "desc": "uma por linha", "color": "#64748b", "important": False},
        {"name": "LocalizaÃ§Ã£o", "desc": "cidade ou paÃ­s", "color": "#64748b", "important": False},
        {"name": "Modalidade", "desc": "presencial, remotoâ€¦", "color": "#64748b", "important": False},
        {"name": "Prazo", "desc": "data limite de candidatura", "color": "#64748b", "important": False},
    ]
    score_dims = [
        {
            "name": "CompetÃªncias",
            "pts": "50 pts",
            "desc": "Compara as competÃªncias do candidato com as requeridas pela vaga. Cada competÃªncia que coincide aumenta a pontuaÃ§Ã£o.",
            "bg": "#eff6ff", "border": "#bfdbfe", "color": "#1d4ed8",
            "text_color": "#1e40af", "bar_bg": "#dbeafe", "pct": 50,
        },
        {
            "name": "ExperiÃªncia",
            "pts": "30 pts",
            "desc": "Compara os anos de experiÃªncia do candidato com o mÃ­nimo exigido. PontuaÃ§Ã£o proporcional atÃ© ao mÃ¡ximo.",
            "bg": "#f5f3ff", "border": "#ddd6fe", "color": "#7c3aed",
            "text_color": "#5b21b6", "bar_bg": "#ede9fe", "pct": 30,
        },
        {
            "name": "FormaÃ§Ã£o",
            "pts": "20 pts",
            "desc": "Verifica se o nÃ­vel acadÃ©mico do candidato corresponde ao mÃ­nimo definido na vaga.",
            "bg": "#f0fdf4", "border": "#bbf7d0", "color": "#15803d",
            "text_color": "#166534", "bar_bg": "#dcfce7", "pct": 20,
        },
    ]
    pipeline_stages = [
        {"name": "Candidatura", "icon": "fa-inbox", "color": "#1d4ed8", "bg": "#eff6ff", "border": "#bfdbfe"},
        {"name": "Em Triagem", "icon": "fa-magnifying-glass", "color": "#8b5cf6", "bg": "#f5f3ff", "border": "#ddd6fe"},
        {"name": "Entrevista", "icon": "fa-comments", "color": "#0891b2", "bg": "#ecfeff", "border": "#a5f3fc"},
        {"name": "Proposta", "icon": "fa-file-signature", "color": "#f59e0b", "bg": "#fffbeb", "border": "#fde68a"},
        {"name": "Contratado", "icon": "fa-circle-check", "color": "#15803d", "bg": "#f0fdf4", "border": "#bbf7d0"},
        {"name": "Rejeitado", "icon": "fa-circle-xmark", "color": "#dc2626", "bg": "#fef2f2", "border": "#fecaca"},
    ]
    return render(request, "ajuda/ajuda.html", {
        "steps": steps,
        "vaga_fields": vaga_fields,
        "score_dims": score_dims,
        "pipeline_stages": pipeline_stages,
    })

