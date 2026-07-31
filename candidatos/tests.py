from django.test import TestCase
from core.scorer import calcular_fit, _score_deterministic, _normalize, _synonym_key
from core.parser import _parse_deterministic


# ---------------------------------------------------------------------------
# Scorer tests
# ---------------------------------------------------------------------------

VAGA_COMPLETA = {
    "titulo": "Analista de Dados",
    "competencias_requeridas": ["python", "sql", "power bi"],
    "anos_experiencia_min": 3,
    "nivel_formacao": "licenciatura",
}

CANDIDATO_PERFEITO = {
    "nome": "Ana Silva",
    "competencias": ["python", "sql", "power bi"],
    "experiencia_anos": 5,
    "formacao": ["Licenciatura em Informática"],
    "idiomas": ["português"],
    "resumo": "",
}


class ScoreTotalTests(TestCase):
    def test_perfeito_score_is_100(self):
        res = _score_deterministic(CANDIDATO_PERFEITO, VAGA_COMPLETA)
        self.assertEqual(res["score_total"], 100)

    def test_sem_competencias_penaliza(self):
        cand = {**CANDIDATO_PERFEITO, "competencias": []}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        self.assertEqual(res["pontuacao_detalhada"]["competencias"], 0)

    def test_experiencia_abaixo_do_minimo_penaliza(self):
        cand = {**CANDIDATO_PERFEITO, "experiencia_anos": 1}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        pts = res["pontuacao_detalhada"]["experiencia"]
        self.assertLess(pts, 25)

    def test_experiencia_exata_vale_25(self):
        cand = {**CANDIDATO_PERFEITO, "experiencia_anos": 3}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        self.assertEqual(res["pontuacao_detalhada"]["experiencia"], 25)

    def test_experiencia_acima_1_5x_vale_30(self):
        cand = {**CANDIDATO_PERFEITO, "experiencia_anos": 6}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        self.assertEqual(res["pontuacao_detalhada"]["experiencia"], 30)

    def test_vaga_sem_minimo_experiencia_vale_25(self):
        vaga = {**VAGA_COMPLETA, "anos_experiencia_min": 0}
        res = _score_deterministic(CANDIDATO_PERFEITO, vaga)
        self.assertEqual(res["pontuacao_detalhada"]["experiencia"], 25)

    def test_formacao_adequada_vale_20(self):
        res = _score_deterministic(CANDIDATO_PERFEITO, VAGA_COMPLETA)
        self.assertEqual(res["pontuacao_detalhada"]["formacao"], 20)

    def test_formacao_nao_confirmada_vale_5(self):
        cand = {**CANDIDATO_PERFEITO, "formacao": []}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        self.assertEqual(res["pontuacao_detalhada"]["formacao"], 5)

    def test_nivel_alinhamento_alto(self):
        res = _score_deterministic(CANDIDATO_PERFEITO, VAGA_COMPLETA)
        self.assertEqual(res["nivel_alinhamento"], "Alto Alinhamento")
        self.assertEqual(res["cor"], "green")

    def test_nivel_alinhamento_baixo(self):
        cand = {**CANDIDATO_PERFEITO, "competencias": [], "experiencia_anos": 0, "formacao": []}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        self.assertEqual(res["nivel_alinhamento"], "Baixo Alinhamento")
        self.assertEqual(res["cor"], "red")

    def test_vaga_sem_competencias_vale_25(self):
        vaga = {**VAGA_COMPLETA, "competencias_requeridas": []}
        res = _score_deterministic(CANDIDATO_PERFEITO, vaga)
        self.assertEqual(res["pontuacao_detalhada"]["competencias"], 25)

    def test_resultado_tem_campos_obrigatorios(self):
        res = _score_deterministic(CANDIDATO_PERFEITO, VAGA_COMPLETA)
        for field in ("score_total", "pontuacao_detalhada", "nivel_alinhamento", "cor", "explicacao"):
            self.assertIn(field, res)

    def test_score_nunca_excede_100(self):
        res = _score_deterministic(CANDIDATO_PERFEITO, VAGA_COMPLETA)
        self.assertLessEqual(res["score_total"], 100)

    def test_score_nunca_negativo(self):
        cand = {**CANDIDATO_PERFEITO, "competencias": [], "experiencia_anos": 0, "formacao": []}
        res = _score_deterministic(cand, VAGA_COMPLETA)
        self.assertGreaterEqual(res["score_total"], 0)


class SynonymMatchingTests(TestCase):
    def test_ingles_matches_english(self):
        key_ing = _synonym_key("inglês")
        key_eng = _synonym_key("english")
        self.assertEqual(key_ing, key_eng)

    def test_rh_matches_recursos_humanos(self):
        key_rh = _synonym_key("rh")
        key_full = _synonym_key("recursos humanos")
        self.assertEqual(key_rh, key_full)

    def test_power_bi_variants_match(self):
        k1 = _synonym_key("power bi")
        k2 = _synonym_key("powerbi")
        k3 = _synonym_key("power-bi")
        self.assertEqual(k1, k2)
        self.assertEqual(k2, k3)

    def test_normalize_strips_accents(self):
        self.assertEqual(_normalize("ação"), "acao")
        self.assertEqual(_normalize("saúde"), "saude")

    def test_synonym_matching_in_score(self):
        vaga = {**VAGA_COMPLETA, "competencias_requeridas": ["inglês"]}
        cand = {**CANDIDATO_PERFEITO, "competencias": ["english"]}
        res = _score_deterministic(cand, vaga)
        self.assertEqual(res["pontuacao_detalhada"]["competencias"], 50)


# ---------------------------------------------------------------------------
# Deterministic parser tests
# ---------------------------------------------------------------------------

class CVParserTests(TestCase):
    CV_SAMPLE = """
    Maria Cardoso
    maria.cardoso@example.com
    +258 84 123 4567

    Licenciatura em Gestão de Recursos Humanos - Universidade Eduardo Mondlane (2015)
    Mestrado em Administração Pública (2018)

    Experiência Profissional:
    Técnica de RH — Ministério da Saúde (2019 - presente)
    Consultora — UNICEF (2016 - 2019)

    Competências: gestão de projetos, Excel, inglês, comunicação
    """

    def test_email_extraido(self):
        res = _parse_deterministic(self.CV_SAMPLE)
        self.assertEqual(res["email"], "maria.cardoso@example.com")

    def test_telefone_extraido(self):
        res = _parse_deterministic(self.CV_SAMPLE)
        self.assertIsNotNone(res["telefone"])

    def test_nome_extraido(self):
        res = _parse_deterministic(self.CV_SAMPLE)
        self.assertIn("Maria", res["nome"])

    def test_competencias_extraidas(self):
        res = _parse_deterministic(self.CV_SAMPLE)
        self.assertIsInstance(res["competencias"], list)

    def test_experiencia_calculada_por_intervalos(self):
        res = _parse_deterministic(self.CV_SAMPLE)
        self.assertGreater(res["experiencia_anos"], 0)

    def test_formacao_extraida(self):
        res = _parse_deterministic(self.CV_SAMPLE)
        self.assertIsInstance(res["formacao"], list)

    def test_resultado_nunca_levanta_excecao(self):
        for text in ["", "   ", "123", "CV\nSem estrutura nenhuma"]:
            try:
                _parse_deterministic(text)
            except Exception as e:
                self.fail(f"_parse_deterministic() raised {e} for input: {text!r}")
