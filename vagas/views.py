import json
import sys
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Vaga

# Make sure core/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def org_vagas(request):
    return Vaga.objects.filter(organisation=request.user.organisation)


def vaga_list(request):
    vagas = org_vagas(request).order_by("-created_at")
    return render(request, "vagas/list.html", {"vagas": vagas})


def vaga_create(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            messages.error(request, "O tÃ­tulo da vaga Ã© obrigatÃ³rio.")
            return render(request, "vagas/create.html")

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        responsabilidades_raw = request.POST.get("responsabilidades_input", "")
        responsabilidades = [r.strip().lstrip("â€¢").strip() for r in responsabilidades_raw.splitlines() if r.strip()]

        vaga = Vaga.objects.create(
            organisation=request.user.organisation,
            titulo=titulo,
            organizacao=request.POST.get("organizacao", "").strip(),
            departamento=request.POST.get("departamento", "Outro"),
            local=request.POST.get("local", "").strip(),
            modalidade=request.POST.get("modalidade", "Presencial"),
            nivel_formacao=request.POST.get("nivel_formacao", "").lower(),
            anos_experiencia_min=int(request.POST.get("anos_experiencia_min", 0) or 0),
            tipo_contrato=request.POST.get("tipo_contrato", "Tempo Inteiro"),
            salario=request.POST.get("salario", "").strip(),
            prazo_candidatura=request.POST.get("prazo_candidatura", "").strip(),
            competencias_requeridas=competencias,
            responsabilidades=responsabilidades,
            descricao=request.POST.get("descricao", "").strip(),
            origem="Manual",
            created_by=request.user,
        )
        messages.success(request, f"Vaga '{vaga.titulo}' criada com sucesso!")
        return redirect("vaga_list")

    return render(request, "vagas/create.html")


def vaga_detail(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    return render(request, "vagas/detail.html", {"vaga": vaga})


def vaga_edit(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    if request.method == "POST":
        titulo = request.POST.get("titulo", "").strip()
        if not titulo:
            messages.error(request, "O tÃ­tulo da vaga Ã© obrigatÃ³rio.")
            return render(request, "vagas/edit.html", {"vaga": vaga})

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        responsabilidades_raw = request.POST.get("responsabilidades_input", "")
        responsabilidades = [r.strip().lstrip("â€¢").strip() for r in responsabilidades_raw.splitlines() if r.strip()]

        vaga.titulo = titulo
        vaga.organizacao = request.POST.get("organizacao", "").strip()
        vaga.departamento = request.POST.get("departamento", "Outro")
        vaga.local = request.POST.get("local", "").strip()
        vaga.modalidade = request.POST.get("modalidade", "Presencial")
        vaga.estado = request.POST.get("estado", "Aberta")
        vaga.nivel_formacao = request.POST.get("nivel_formacao", "").lower()
        vaga.anos_experiencia_min = int(request.POST.get("anos_experiencia_min", 0) or 0)
        vaga.tipo_contrato = request.POST.get("tipo_contrato", "Tempo Inteiro")
        vaga.salario = request.POST.get("salario", "").strip()
        vaga.prazo_candidatura = request.POST.get("prazo_candidatura", "").strip()
        vaga.competencias_requeridas = competencias
        vaga.responsabilidades = responsabilidades
        vaga.descricao = request.POST.get("descricao", "").strip()
        vaga.save()
        messages.success(request, f"Vaga '{vaga.titulo}' actualizada.")
        return redirect("vaga_detail", pk=vaga.pk)

    return render(request, "vagas/edit.html", {"vaga": vaga})


def vaga_delete(request, pk):
    vaga = get_object_or_404(org_vagas(request), pk=pk)
    if request.method == "POST":
        vaga.delete()
        messages.success(request, f"Vaga '{vaga.titulo}' eliminada.")
        return redirect("vaga_list")
    return render(request, "vagas/confirm_delete.html", {"vaga": vaga})


@require_POST
def parse_tor_view(request):
    """
    HTMX endpoint â€” called when user uploads a ToR file.
    Step 1: extract text and return preview.
    """
    from django.conf import settings
    uploaded = request.FILES.get("tor_file")
    if not uploaded:
        return HttpResponse('<div class="alert-error">Nenhum ficheiro recebido.</div>')

    try:
        from core.parser import extract_text_from_file
        texto = extract_text_from_file(uploaded)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro ao extrair texto: {e}</div>')

    if not texto.strip():
        return HttpResponse('<div class="alert-error">NÃ£o foi possÃ­vel extrair texto. O ficheiro pode ser uma imagem digitalizada.</div>')

    # Return the text preview + hidden field + AI analysis button
    texto_preview = texto[:4000]
    return render(request, "vagas/_tor_preview.html", {
        "texto": texto_preview,
        "texto_completo": texto,
    })


@require_POST
def analyse_tor_view(request):
    """
    HTMX endpoint â€” called when user clicks 'Analisar com IA'.
    Sends text to Grok and returns pre-filled form fields.
    """
    from django.conf import settings
    texto = request.POST.get("texto_completo", "")
    if not texto.strip():
        return HttpResponse('<div class="alert-error">Texto nÃ£o encontrado. Carregue o ficheiro novamente.</div>')

    try:
        os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
        os.environ["LLM_ENGINE"] = settings.LLM_ENGINE

        from core.parser import parse_tor
        extraido = parse_tor(texto)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro na anÃ¡lise IA: {e}</div>')

    return render(request, "vagas/_form_fields.html", {
        "tor": extraido,
        "metodo": extraido.get("metodo_extracao", "IA"),
    })

