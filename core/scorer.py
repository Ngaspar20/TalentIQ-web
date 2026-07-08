# core/scorer.py — Candidate fit scoring engine for TalentIQ

import json
import re as _re
import logging
from typing import Dict, Any, List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
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
