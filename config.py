"""
Compatibility shim — core/ was written for the desktop app and reads from this module.
In Django we pull LLM settings from Django settings; everything else is copied verbatim.
"""
import os

# Pull from Django settings if available, otherwise fall back to env vars
try:
    from django.conf import settings as _dj
    GROK_API_KEY = _dj.GROK_API_KEY
    LLM_ENGINE = _dj.LLM_ENGINE
except Exception:
    GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
    LLM_ENGINE = os.environ.get("LLM_ENGINE", "grok")

GROK_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-3"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o"

SCORE_ALTO = 75
SCORE_MEDIO = 50

SKILLS_KEYWORDS = [
    "python", "java", "javascript", "sql", "excel", "power bi", "tableau",
    "r", "machine learning", "inteligência artificial", "data science",
    "gestão de projetos", "project management", "scrum", "agile",
    "saúde pública", "epidemiologia", "monitoria", "avaliação", "m&a",
    "hiv", "ats", "smaj", "sisma", "dhis2",
    "liderança", "comunicação", "trabalho em equipa", "resolução de problemas",
    "negociação", "gestão de equipa", "formação", "treinamento",
    "inglês", "português", "francês", "espanhol", "english", "french",
    "contabilidade", "finanças", "orçamento", "recursos humanos", "rh",
    "recrutamento", "seleção", "marketing", "vendas", "logística",
]

EDUCATION_KEYWORDS = [
    "licenciatura", "mestrado", "doutoramento", "mba", "bacharel",
    "pós-graduação", "curso técnico", "certificação", "diploma",
    "bachelor", "master", "phd", "degree", "certificate",
    "universidade", "faculdade", "instituto", "university", "college",
]

JOB_TITLE_KEYWORDS = [
    "gestor", "gerente", "diretor", "coordenador", "analista", "técnico",
    "consultor", "especialista", "supervisor", "assistente", "oficial",
    "manager", "director", "coordinator", "analyst", "consultant",
    "specialist", "supervisor", "assistant", "officer", "engineer",
]
