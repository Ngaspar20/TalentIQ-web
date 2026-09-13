# core/scorer.py — Candidate fit scoring engine for TalentIQ

import json
import re as _re
import logging
from typing import Dict, Any, List
try:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config
except Exception:
    from types import SimpleNamespace
    from django.conf import settings as _s
    config = SimpleNamespace(
        LLM_ENGINE=getattr(_s, "LLM_ENGINE", "deterministic"),
        GROK_API_KEY=getattr(_s, "GROK_API_KEY", ""),
        GROK_BASE_URL="https://api.x.ai/v1",
        GROK_MODEL="grok-3",
        OPENAI_API_KEY="",
        OPENAI_MODEL="gpt-4o",
        SCORE_ALTO=75,
        SCORE_MEDIO=50,
    )
from core.llm import get_llm_response

logger = logging.getLogger(__name__)

# PT/EN synonym groups — any term in a group matches any other term in the same group
_SYNONYM_GROUPS = [
    {"machine learning", "ml", "aprendizagem automática"},
    {"power bi", "powerbi", "power-bi"},
    {"gestão de projetos", "project management", "gestão de projectos"},
    {"recursos humanos", "rh", "human resources", "hr"},
    {"saúde pública", "public health", "saude publica"},
    {"monitoria", "monitoring", "m&e", "m&a", "monitorização"},
    {"avaliação", "evaluation", "assessment"},
    {"trabalho em equipa", "teamwork", "team work"},
    {"resolução de problemas", "problem solving"},
    {"liderança", "leadership"},
    {"comunicação", "communication"},
    {"negociação", "negotiation"},
    {"formação", "treinamento", "training"},
    {"inglês", "english", "ingles"},
    {"português", "portuguese"},
    {"francês", "french", "frances"},
    {"espanhol", "spanish"},
    {"microsoft excel", "excel"},
    {"inteligência artificial", "ia", "artificial intelligence", "ai"},
    {"data science", "ciência de dados"},
    {"sql", "structured query language"},
    {"scrum", "agile", "metodologias ágeis"},
    {"python", "python3"},
    {"r", "rstudio", "linguagem r"},
    {"tableau", "tableau software"},
    {"dhis2", "district health information system"},
    {"sisma", "sistema de informação de saúde"},
    {"pepfar", "president's emergency plan for aids relief"},
    {"postgresql", "postgres"},
    {"epidemiologia", "epidemiology"},
]

_LEVEL_WORDS = {
    "avancado", "avancada", "avancados", "avancadas",
    "intermediario", "intermediaria", "intermedio", "intermedia",
    "basico", "basica",
    "advanced", "intermediate", "basic",
    "nivel", "nível", "level",
    "eficaz", "eficazes", "efetivo", "efetiva",
}


def _normalize(term: str) -> str:
    """Lowercase, strip, remove accents."""
    import unicodedata
    s = term.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def _extract_core(term: str) -> str:
    """
    Strip LLM-style qualifiers from a competência phrase, returning the base skill name.

    Handles patterns like:
      "Python (pandas, numpy, matplotlib) — nível avançado"  → "python"
      "SQL — nível avançado (PostgreSQL ou MySQL)"           → "sql"
      "Power BI — nível avançado"                           → "power bi"
      "Excel Avançado"                                       → "excel"
      "matplotlib) — nível avançado"  (broken token)        → "matplotlib"
    """
    s = term
    # Remove complete and incomplete parenthetical content
    s = _re.sub(r'\([^)]*\)?', '', s)
    # Remove stray closing parens
    s = _re.sub(r'\)', '', s)
    # Remove everything from em-dash / en-dash onward
    s = _re.sub(r'\s*[—–]\s*.*', '', s)
    # Remove " - nível ..." style suffix
    s = _re.sub(r'\s+-\s+n[íi]vel\b.*', '', s, flags=_re.IGNORECASE)
    # Remove stray opening parens
    s = _re.sub(r'\(', '', s)
    # Strip individual level/qualifier words
    words = s.split()
    words = [w for w in words if _normalize(w) not in _LEVEL_WORDS]
    s = ' '.join(words)
    return s.strip(' ,')


def _synonym_key(term: str) -> str:
    """Return the canonical synonym key for a base term."""
    norm = _normalize(term)
    for group in _SYNONYM_GROUPS:
        if norm in {_normalize(g) for g in group}:
            return _normalize(min(group))
    return norm


def _expand_competencia(term: str) -> list:
    """
    Expand a rich LLM competência phrase into one or more matchable synonym keys.

    Two expansion strategies:
    1. Strip qualifiers to get the base concept:
       "Python (pandas, numpy)" → ["python"]
    2. Split multi-skill entries:
       "Power BI, Tableau, Excel Avançado" → ["power bi", "tableau", "excel"]
    """
    core = _extract_core(term)
    if not core:
        return [_synonym_key(term)]
    # If the core itself contains commas it is a multi-skill entry → expand each part
    if ',' in core:
        parts = [p.strip() for p in core.split(',') if p.strip()]
        return [_synonym_key(p) for p in parts]
    return [_synonym_key(core)]


def _competencia_matches(vaga_key: str, cand_keys: set) -> bool:
    """
    Check if a vaga competência key matches any candidate key.
    Falls back to substring containment for long descriptive phrases.
    """
    if vaga_key in cand_keys:
        return True
    # Substring fallback: handles "comunicação eficaz…" ⊃ "comunicação"
    if len(vaga_key) >= 5:
        for ck in cand_keys:
            if vaga_key in ck or (len(ck) >= 5 and ck in vaga_key):
                return True
    return False

# Education level hierarchy for graduated scoring
_EDU_LEVELS = {
    "curso técnico": 1, "certificação": 1,
    "licenciatura": 2, "bacharel": 2,
    "mestrado": 3, "mba": 3,
    "doutoramento": 4, "phd": 4,
}


def calcular_fit(candidato: Dict[str, Any], vaga: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate fit score between a candidate and a job.
    Returns score (0-100), breakdown, and explanation.
    """
    if config.LLM_ENGINE != "deterministic":
        resultado = _score_with_llm(candidato, vaga)
        if resultado:
            resultado["metodo"] = f"LLM ({config.LLM_ENGINE})"
            return resultado

    resultado = _score_deterministic(candidato, vaga)
    resultado["metodo"] = "Determinístico"
    return resultado


def _score_deterministic(candidato: Dict, vaga: Dict) -> Dict[str, Any]:
    """
    Deterministic scoring across 3 dimensions:
    - Competências (50%)
    - Experiência em anos (30%)
    - Formação (20%)
    """
    pontos = {}
    explicacao = []

    # --- Competências (50 points) — synonym-aware + LLM-phrase-aware matching ---
    # Build deduplicated vaga requirement list: (original_label, [expanded_keys])
    vaga_reqs = []
    seen_vaga_keys: set = set()
    for c in (vaga.get("competencias_requeridas") or []):
        exp = [k for k in _expand_competencia(c) if k]
        new_keys = [k for k in exp if k not in seen_vaga_keys]
        if new_keys:
            vaga_reqs.append((c, new_keys))
            seen_vaga_keys.update(new_keys)

    # Build candidate key set — expand multi-skill entries and rich phrases
    keys_candidato: set = set()
    for c in (candidato.get("competencias") or []):
        keys_candidato.update(k for k in _expand_competencia(c) if k)

    if vaga_reqs:
        matched = [(label, keys) for label, keys in vaga_reqs
                   if any(_competencia_matches(k, keys_candidato) for k in keys)]
        gap_labels = [label for label, keys in vaga_reqs
                      if not any(_competencia_matches(k, keys_candidato) for k in keys)]
        n_matched = len(matched)
        n_total = len(vaga_reqs)
        score_comp = round((n_matched / n_total) * 50)
        pontos["competencias"] = score_comp
        explicacao.append(
            f"✅ Competências: {n_matched}/{n_total} correspondências "
            f"({score_comp}/50 pts)"
        )
        if gap_labels:
            explicacao.append(f"⚠️ Competências em falta: {', '.join(gap_labels)}")
    else:
        pontos["competencias"] = 25
        explicacao.append("ℹ️ Nenhuma competência específica definida para a vaga (25/50 pts)")

    # --- Experiência (30 points) — graduated: meets min=25, exceeds=30 ---
    anos_requeridos = vaga.get("anos_experiencia_min") or 0
    anos_candidato = candidato.get("experiencia_anos") or 0

    if anos_requeridos == 0:
        score_exp = 25
        explicacao.append("ℹ️ Experiência mínima não definida (25/30 pts)")
    elif anos_candidato >= anos_requeridos * 1.5:
        score_exp = 30
        explicacao.append(
            f"✅ Experiência: {anos_candidato} anos — significativamente acima do mínimo "
            f"({anos_requeridos}) (30/30 pts)"
        )
    elif anos_candidato >= anos_requeridos:
        score_exp = 25
        explicacao.append(
            f"✅ Experiência: {anos_candidato} anos (mínimo: {anos_requeridos}) (25/30 pts)"
        )
    else:
        ratio = anos_candidato / anos_requeridos
        score_exp = round(ratio * 25)
        explicacao.append(
            f"⚠️ Experiência insuficiente: {anos_candidato} anos (mínimo: {anos_requeridos}) "
            f"({score_exp}/30 pts)"
        )
    pontos["experiencia"] = score_exp

    # --- Formação (20 points) — graduated by education hierarchy ---
    nivel_requerido = (vaga.get("nivel_formacao") or "").lower().strip()
    formacao_candidato = " ".join(candidato.get("formacao") or []).lower()

    nivel_map = {
        "licenciatura": ["licenciatura", "bacharel", "bachelor", "degree"],
        "mestrado": ["mestrado", "master", "mba"],
        "doutoramento": ["doutoramento", "phd", "doutor", "doctorate"],
        "curso técnico": ["técnico", "tecnico", "certificate", "certificação", "certificacao", "diploma"],
    }

    score_form = 0
    if not nivel_requerido:
        score_form = 15
        explicacao.append("ℹ️ Formação mínima não definida (15/20 pts)")
    else:
        nivel_req_rank = _EDU_LEVELS.get(nivel_requerido, 2)
        keywords = nivel_map.get(nivel_requerido, [nivel_requerido])

        if any(kw in formacao_candidato for kw in keywords):
            score_form = 20
            explicacao.append(f"✅ Formação adequada: {nivel_requerido} (20/20 pts)")
        else:
            # Check if candidate has a lower level — graduated penalty
            cand_rank = 0
            for kw_list, rank in [(nivel_map.get(n, []), r)
                                   for n, r in _EDU_LEVELS.items()]:
                if any(kw in formacao_candidato for kw in kw_list):
                    cand_rank = max(cand_rank, rank)

            if cand_rank == 0:
                score_form = 5
                explicacao.append(f"⚠️ Formação não confirmada para: {nivel_requerido} (5/20 pts)")
            elif cand_rank >= nivel_req_rank:
                score_form = 18
                explicacao.append(f"✅ Formação acima do requisito (18/20 pts)")
            else:
                gap = nivel_req_rank - cand_rank
                score_form = max(5, 15 - gap * 5)
                explicacao.append(
                    f"⚠️ Formação abaixo do requisito ({nivel_requerido}) — {score_form}/20 pts"
                )
    pontos["formacao"] = score_form

    # --- Total ---
    total = pontos["competencias"] + pontos["experiencia"] + pontos["formacao"]

    # Classify
    if total >= config.SCORE_ALTO:
        nivel = "Alto Alinhamento"
        cor = "green"
    elif total >= config.SCORE_MEDIO:
        nivel = "Alinhamento Médio"
        cor = "orange"
    else:
        nivel = "Baixo Alinhamento"
        cor = "red"

    return {
        "score_total": total,
        "pontuacao_detalhada": pontos,
        "nivel_alinhamento": nivel,
        "cor": cor,
        "explicacao": explicacao,
    }


# ---------------------------------------------------------------------------
# Rubric-based evaluation: full CV vs full ToR against a grelha de avaliação
# ---------------------------------------------------------------------------

_RESULTADO_FACTOR = {"cumpre": 1.0, "parcial": 0.5, "nao_cumpre": 0.0}

_NIVEL_KEYWORDS = {
    "curso técnico": ["tecnico", "certificate", "certificacao", "diploma"],
    "licenciatura": ["licenciatura", "licenciado", "bacharel", "bachelor", "degree", "engenheiro"],
    "mestrado": ["mestrado", "master", "mba", "msc"],
    "doutoramento": ["doutoramento", "phd", "doutor", "doctorate"],
}

_STOPWORDS = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "com", "para", "por", "e", "ou",
    "a", "o", "as", "os", "um", "uma", "que", "ser", "ter", "the", "and", "of", "in", "with", "for",
    "to", "on", "at", "or", "an", "is", "minimo", "minima", "anos", "ano", "years", "year",
    "experiencia", "experience", "conhecimento", "conhecimentos", "capacidade", "competencia",
    "competencias", "skills", "skill", "nivel", "level", "forte", "fortes", "bom", "boa",
    "relevante", "relevantes", "profissional", "area", "areas", "idioma", "lingua", "fluente",
    "fluencia", "dominio", "solido", "solida", "comprovada", "comprovado", "demonstrada",
}


def avaliar_por_criterios(cv_texto: str, tor_texto: str, criterios: List[Dict[str, Any]],
                          candidato: Dict[str, Any] = None) -> Dict[str, Any]:
    """Evaluate a CV against a grelha de avaliação. Returns {} if the rubric is empty.

    Result: {score_total, metodo, criterios: [{criterio, categoria, essencial, peso,
    resultado, evidencia, comentario, pontos}], essenciais_falhados: [labels]}
    """
    criterios = [c for c in (criterios or []) if str(c.get("criterio") or "").strip()]
    if not criterios:
        return {}
    avaliacoes = None
    metodo = f"LLM ({config.LLM_ENGINE})"
    if config.LLM_ENGINE != "deterministic":
        avaliacoes = _avaliar_criterios_llm(cv_texto or "", tor_texto or "", criterios)
    if not avaliacoes:
        avaliacoes = _avaliar_criterios_deterministic(cv_texto or "", criterios, candidato or {})
        metodo = "Determinístico"
    return _consolidar_avaliacao(criterios, avaliacoes, metodo)


def _consolidar_avaliacao(criterios, avaliacoes, metodo) -> Dict[str, Any]:
    linhas, total, maximo, falhados = [], 0.0, 0, []
    for crit, av in zip(criterios, avaliacoes):
        av = av or {}
        resultado = av.get("resultado") if av.get("resultado") in _RESULTADO_FACTOR else "nao_cumpre"
        try:
            peso = max(1, min(5, int(crit.get("peso") or 3)))
        except (TypeError, ValueError):
            peso = 3
        essencial = bool(crit.get("essencial"))
        pontos = peso * _RESULTADO_FACTOR[resultado]
        total += pontos
        maximo += peso
        # Essential criteria are eliminatory: partial credit counts toward the
        # score, but anything short of "cumpre" still blocks the shortlist.
        if essencial and resultado != "cumpre":
            falhados.append(crit["criterio"])
        linhas.append({
            "criterio": crit["criterio"],
            "categoria": crit.get("categoria") or "outro",
            "essencial": essencial,
            "peso": peso,
            "resultado": resultado,
            "evidencia": str(av.get("evidencia") or "")[:400],
            "comentario": str(av.get("comentario") or "")[:400],
            "pontos": pontos,
        })
    score = round(100 * total / maximo) if maximo else 0
    return {"score_total": score, "metodo": metodo, "criterios": linhas,
            "essenciais_falhados": falhados}


def _normalizar_resultado(valor) -> str:
    v = _normalize(str(valor or ""))
    if "parcial" in v or "partial" in v:
        return "parcial"
    if v.startswith(("nao", "not")) or v in ("no", "false", "0"):
        return "nao_cumpre"
    if "cumpre" in v or "met" in v or v in ("sim", "yes", "true", "1"):
        return "cumpre"
    return "nao_cumpre"


def _avaliar_criterios_llm(cv_texto: str, tor_texto: str, criterios: list):
    system = (
        "Você é um especialista em recrutamento e seleção. Avalia CVs contra uma grelha de "
        "critérios de forma rigorosa e baseada em evidência. Responda APENAS com JSON válido."
    )
    grelha = "\n".join(
        f'{i}. {c["criterio"]} [{"ESSENCIAL" if c.get("essencial") else "desejável"}, peso {c.get("peso", 3)}]'
        for i, c in enumerate(criterios, 1)
    )
    prompt = f"""Avalia o CV abaixo contra cada critério da grelha, usando os Termos de Referência como contexto.

TERMOS DE REFERÊNCIA:
{tor_texto[:12000]}

GRELHA DE AVALIAÇÃO:
{grelha}

CV DO CANDIDATO:
{cv_texto[:20000]}

Para CADA critério (todos os {len(criterios)}), devolve um objecto numa lista JSON:
{{
  "n": número do critério,
  "resultado": "cumpre" | "parcial" | "nao_cumpre",
  "evidencia": "citação curta e literal do CV que sustenta o resultado (vazio se não houver)",
  "comentario": "uma frase em português a justificar"
}}

Regras:
- Baseia-te exclusivamente no que está escrito no CV. Não infiras nem assumas.
- Se o CV não menciona o critério, o resultado é "nao_cumpre" e a evidência fica vazia.
- "parcial" quando o CV mostra o requisito de forma incompleta (menos anos, nível inferior, experiência adjacente).
- Devolve apenas a lista JSON."""
    try:
        response = get_llm_response(prompt, system)
        if not response:
            return None
        clean = _re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
        data = json.loads(clean)
        if isinstance(data, dict):
            data = data.get("avaliacoes") or data.get("criterios") or data.get("resultados") or []
        if not isinstance(data, list):
            return None
        por_n = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                n = int(item.get("n"))
            except (TypeError, ValueError):
                continue
            item["resultado"] = _normalizar_resultado(item.get("resultado"))
            por_n[n] = item
        if not por_n:
            return None
        return [por_n.get(i, {"resultado": "nao_cumpre", "comentario": "Não avaliado pelo modelo."})
                for i in range(1, len(criterios) + 1)]
    except Exception as e:
        logger.warning(f"LLM avaliação por critérios falhou, usando fallback: {e}")
        return None


def _avaliar_criterios_deterministic(cv_texto: str, criterios: list, candidato: Dict) -> list:
    cv_norm = _normalize(cv_texto)
    linhas_orig = [l.strip() for l in cv_texto.split("\n") if l.strip()]
    linhas_norm = [_normalize(l) for l in linhas_orig]

    def linha_com(termos):
        melhor, melhor_n = "", 0
        for orig, norm in zip(linhas_orig, linhas_norm):
            n = sum(1 for t in termos if t and t in norm)
            if n > melhor_n:
                melhor, melhor_n = orig, n
        return melhor[:200]

    out = []
    for c in criterios:
        cat = c.get("categoria") or "outro"
        norm = _normalize(c["criterio"])

        if cat == "experiencia":
            m = _re.search(r"(\d+)\s*(?:anos?|years?)", norm)
            req = int(m.group(1)) if m else 0
            anos = candidato.get("experiencia_anos") or 0
            if not anos:
                m2 = _re.search(r"(\d+)\s*(?:anos?|years?)\s+(?:de\s+)?(?:experiencia|experience)", cv_norm)
                anos = int(m2.group(1)) if m2 else 0
            if req == 0:
                resultado = "parcial" if anos else "nao_cumpre"
            elif anos >= req:
                resultado = "cumpre"
            elif anos >= req * 0.6:
                resultado = "parcial"
            else:
                resultado = "nao_cumpre"
            out.append({
                "resultado": resultado,
                "evidencia": f"{anos} anos de experiência identificados no CV" if anos else "",
                "comentario": f"Requisito: {req} anos." if req else "Anos requeridos não especificados no critério.",
            })
            continue

        if cat == "formacao":
            req_rank = min((r for k, r in _EDU_LEVELS.items() if _normalize(k) in norm), default=2)
            cand_rank, termo_hit = 0, ""
            for nivel, kws in _NIVEL_KEYWORDS.items():
                for kw in kws:
                    if kw in cv_norm and _EDU_LEVELS.get(nivel, 0) > cand_rank:
                        cand_rank, termo_hit = _EDU_LEVELS[nivel], kw
            if cand_rank and cand_rank >= req_rank:
                resultado = "cumpre"
            elif cand_rank:
                resultado = "parcial"
            else:
                resultado = "nao_cumpre"
            out.append({
                "resultado": resultado,
                "evidencia": linha_com([termo_hit]) if termo_hit else "",
                "comentario": "Nível de formação verificado por palavras-chave.",
            })
            continue

        tokens = [t for t in _re.findall(r"[a-z0-9&+#]{3,}", norm) if t not in _STOPWORDS]
        if not tokens:
            out.append({"resultado": "nao_cumpre", "evidencia": "",
                        "comentario": "Critério sem termos verificáveis automaticamente."})
            continue
        hits = []
        for t in tokens:
            alts = {t}
            for g in _SYNONYM_GROUPS:
                gn = {_normalize(x) for x in g}
                if t in gn:
                    alts |= gn
            if any(a in cv_norm for a in alts):
                hits.append(t)
        cov = len(hits) / len(tokens)
        resultado = "cumpre" if cov >= 0.6 else "parcial" if cov >= 0.3 else "nao_cumpre"
        out.append({
            "resultado": resultado,
            "evidencia": linha_com(hits) if hits else "",
            "comentario": f"{len(hits)}/{len(tokens)} termos do critério encontrados no CV.",
        })
    return out


def _score_with_llm(candidato: Dict, vaga: Dict) -> Dict[str, Any]:
    system = (
        "Você é um especialista em recrutamento e seleção. "
        "Avalie o alinhamento entre candidato e vaga. "
        "Responda APENAS com JSON válido."
    )
    prompt = f"""
Avalie o alinhamento entre este candidato e esta vaga. Responda em JSON:
{{
  "score_total": número de 0 a 100,
  "pontuacao_detalhada": {{
    "competencias": número de 0 a 50,
    "experiencia": número de 0 a 30,
    "formacao": número de 0 a 20
  }},
  "nivel_alinhamento": "Alto Alinhamento" | "Alinhamento Médio" | "Baixo Alinhamento",
  "cor": "green" | "orange" | "red",
  "explicacao": ["lista de frases explicando os pontos fortes e lacunas"]
}}

CANDIDATO:
{json.dumps(candidato, ensure_ascii=False, indent=2)}

VAGA:
{json.dumps(vaga, ensure_ascii=False, indent=2)}
"""
    try:
        response = get_llm_response(prompt, system)
        if response:
            clean = response.strip().strip("```json").strip("```").strip()
            return json.loads(clean)
    except Exception as e:
        logger.warning(f"LLM scoring falhou, usando fallback: {e}")
    return {}
