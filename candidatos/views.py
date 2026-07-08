import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Candidato


def org_candidatos(request):
    return Candidato.objects.filter(organisation=request.user.organisation)


def candidato_list(request):
    candidatos = org_candidatos(request).select_related("vaga").order_by("-created_at")
    return render(request, "candidatos/list.html", {"candidatos": candidatos})


def candidato_create(request):
    from vagas.models import Vaga
    if request.method == "POST":
        vaga_id = request.POST.get("vaga_id", "").strip()
        nome = request.POST.get("nome", "").strip()
        if not nome:
            messages.error(request, "O nome do candidato Ã© obrigatÃ³rio.")
            vagas = Vaga.objects.filter(organisation=request.user.organisation, estado="Aberta")
            return render(request, "candidatos/create.html", {"vagas": vagas})

        import json
        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        formacao_raw = request.POST.get("formacao_input", "")
        formacao = [f.strip() for f in formacao_raw.splitlines() if f.strip()]

        idiomas_raw = request.POST.get("idiomas_input", "")
        idiomas = [i.strip() for i in idiomas_raw.split(",") if i.strip()]

        vaga = None
        if vaga_id:
            try:
                vaga = Vaga.objects.get(pk=vaga_id, organisation=request.user.organisation)
            except Vaga.DoesNotExist:
                pass

        candidato = Candidato.objects.create(
            organisation=request.user.organisation,
            vaga=vaga,
            nome=nome,
            email=request.POST.get("email", "").strip(),
            telefone=request.POST.get("telefone", "").strip(),
            experiencia_anos=int(request.POST.get("experiencia_anos", 0) or 0),
            competencias=competencias,
            formacao=formacao,
            idiomas=idiomas,
            resumo=request.POST.get("resumo", "").strip(),
            notas=request.POST.get("notas", "").strip(),
            created_by=request.user,
        )
        messages.success(request, f"Candidato '{candidato.nome}' adicionado com sucesso!")
        return redirect("candidato_list")

    vagas = Vaga.objects.filter(organisation=request.user.organisation, estado="Aberta")
    return render(request, "candidatos/create.html", {"vagas": vagas})


def candidato_detail(request, pk):
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    return render(request, "candidatos/detail.html", {"candidato": candidato})


def candidato_edit(request, pk):
    from vagas.models import Vaga
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    vagas = Vaga.objects.filter(organisation=request.user.organisation).order_by("titulo")
    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        if not nome:
            messages.error(request, "O nome do candidato Ã© obrigatÃ³rio.")
            return render(request, "candidatos/edit.html", {"candidato": candidato, "vagas": vagas})

        competencias_raw = request.POST.get("competencias_input", "")
        competencias = [c.strip().lower() for c in competencias_raw.split(",") if c.strip()]

        formacao_raw = request.POST.get("formacao_input", "")
        formacao = [f.strip() for f in formacao_raw.splitlines() if f.strip()]

        idiomas_raw = request.POST.get("idiomas_input", "")
        idiomas = [i.strip() for i in idiomas_raw.split(",") if i.strip()]

        vaga_id = request.POST.get("vaga_id", "").strip()
        if vaga_id:
            try:
                candidato.vaga = Vaga.objects.get(pk=vaga_id, organisation=request.user.organisation)
            except Vaga.DoesNotExist:
                candidato.vaga = None
        else:
            candidato.vaga = None

        candidato.nome = nome
        candidato.email = request.POST.get("email", "").strip()
        candidato.telefone = request.POST.get("telefone", "").strip()
        candidato.experiencia_anos = int(request.POST.get("experiencia_anos", 0) or 0)
        candidato.etapa = request.POST.get("etapa", "Candidatura Recebida")
        candidato.competencias = competencias
        candidato.formacao = formacao
        candidato.idiomas = idiomas
        candidato.resumo = request.POST.get("resumo", "").strip()
        candidato.notas = request.POST.get("notas", "").strip()
        candidato.save()
        messages.success(request, f"Candidato '{candidato.nome}' actualizado.")
        return redirect("candidato_detail", pk=candidato.pk)

    return render(request, "candidatos/edit.html", {"candidato": candidato, "vagas": vagas})


def candidato_delete(request, pk):
    candidato = get_object_or_404(org_candidatos(request), pk=pk)
    if request.method == "POST":
        candidato.delete()
        messages.success(request, f"Candidato '{candidato.nome}' eliminado.")
        return redirect("candidato_list")
    return render(request, "candidatos/confirm_delete.html", {"candidato": candidato})


@require_POST
def parse_cv_view(request):
    """HTMX â€” extracts text from uploaded CV file and returns preview."""
    uploaded = request.FILES.get("cv_file")
    if not uploaded:
        return HttpResponse('<div class="alert-error">Nenhum ficheiro recebido.</div>')

    try:
        from core.parser import extract_text_from_file
        texto = extract_text_from_file(uploaded)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro ao extrair texto: {e}</div>')

    if not texto.strip():
        return HttpResponse('<div class="alert-error">NÃ£o foi possÃ­vel extrair texto. O ficheiro pode ser uma imagem digitalizada.</div>')

    return render(request, "candidatos/_cv_preview.html", {
        "texto": texto[:4000],
        "texto_completo": texto,
    })


@require_POST
def analyse_cv_view(request):
    """HTMX â€” sends CV text to Grok and returns pre-filled candidate form."""
    from django.conf import settings
    texto = request.POST.get("texto_completo", "")
    if not texto.strip():
        return HttpResponse('<div class="alert-error">Texto nÃ£o encontrado. Carregue o CV novamente.</div>')

    try:
        os.environ["GROK_API_KEY"] = settings.GROK_API_KEY
        os.environ["LLM_ENGINE"] = settings.LLM_ENGINE

        from core.parser import parse_cv
        extraido = parse_cv(texto)
    except Exception as e:
        return HttpResponse(f'<div class="alert-error">Erro na anÃ¡lise IA: {e}</div>')

    return render(request, "candidatos/_cv_form_fields.html", {
        "cv": extraido,
        "metodo": extraido.get("metodo_extracao", "IA"),
    })

