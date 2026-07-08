from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from vagas.models import Vaga
from candidatos.models import Candidato

ETAPAS = ["Candidatura Recebida", "Em Triagem", "Entrevista", "Proposta", "Contratado", "Rejeitado"]

ETAPA_COLORS = {
    "Candidatura Recebida": "#3b82f6",
    "Em Triagem": "#8b5cf6",
    "Entrevista": "#f59e0b",
    "Proposta": "#06b6d4",
    "Contratado": "#10b981",
    "Rejeitado": "#ef4444",
}


def pipeline_view(request):
    vagas = Vaga.objects.filter(organisation=request.user.organisation).order_by("-created_at")
    filtro_vaga = None
    vaga_id = request.GET.get("vaga")
    if vaga_id:
        try:
            filtro_vaga = Vaga.objects.get(pk=vaga_id, organisation=request.user.organisation)
        except Vaga.DoesNotExist:
            pass

    if filtro_vaga:
        candidatos = Candidato.objects.filter(vaga=filtro_vaga).select_related("vaga")
    else:
        candidatos = Candidato.objects.filter(organisation=request.user.organisation).select_related("vaga")

    return render(request, "pipeline/pipeline.html", {
        "vagas": vagas,
        "candidatos": candidatos,
        "etapas": ETAPAS,
        "etapa_colors": ETAPA_COLORS,
        "filtro_vaga": filtro_vaga,
    })


def pipeline_vaga(request, vaga_id):
    vaga = get_object_or_404(Vaga, pk=vaga_id, organisation=request.user.organisation)
    vagas = Vaga.objects.filter(organisation=request.user.organisation)
    candidatos = Candidato.objects.filter(vaga=vaga).select_related("vaga")
    return render(request, "pipeline/pipeline.html", {
        "vagas": vagas,
        "candidatos": candidatos,
        "etapas": ETAPAS,
        "etapa_colors": ETAPA_COLORS,
        "filtro_vaga": vaga,
    })


def mover_etapa(request):
    if request.method == "POST":
        candidato_id = request.POST.get("candidato_id")
        nova_etapa = request.POST.get("etapa")
        candidato = get_object_or_404(Candidato, pk=candidato_id, organisation=request.user.organisation)
        if nova_etapa in ETAPAS:
            candidato.etapa = nova_etapa
            candidato.save(update_fields=["etapa", "updated_at"])
        if request.htmx:
            return HttpResponse(f'<span class="text-green-600 text-sm font-medium">âœ“ Movido para {nova_etapa}</span>')
        messages.success(request, f"{candidato.nome} movido para {nova_etapa}.")
    return JsonResponse({"ok": True})


def pipeline_export(request):
    return HttpResponse("Export not yet implemented", status=501)

