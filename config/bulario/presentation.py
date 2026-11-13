def _adicionar_graus_avaliacao(resultado):
    """Descreve o significado da saída, sem inferir confiança clínica do score."""
    descriptions = {
        "ordinal": "Categoria ordinal de suporte",
        "pontuacao_heuristica": "Pontuação heurística",
        "similaridade_ajustada": "Similaridade de Jaccard ajustada",
        "posterior_modelo": "Probabilidade no modelo parametrizado",
        "probabilidade_modelo": "Probabilidade no classificador",
        "suporte_fuzzy": "Suporte fuzzy (Sugeno)",
        "composicao_max_min": "Grau da composição max–min (Sanchez)",
    }
    score_type = resultado.get("tipo_score", "pontuacao_heuristica")
    resultado["descricao_score"] = descriptions.get(score_type, "Pontuação do modelo")
    for hypothesis in resultado.get("hipoteses", []):
        hypothesis["grau_correspondencia"] = hypothesis.get("categoria_suporte", resultado["descricao_score"])
    mechanisms = {
        "regras": ("Ranqueamento heurístico", "Sintomas incertos não são afirmados"),
        "regras_encadeadas": ("Derivação de hipóteses por regras", "Sintomas incertos não são afirmados"),
        "semantica": ("Consulta ao grafo e similaridade", "Sintomas incertos não são afirmados"),
        "rede_bayesiana": ("Inferência Naive Bayes", "Evidência desconhecida/incerta marginalizada"),
        "fuzzy": ("Inferência Sugeno", "Peso parcial da observação e pertinências graduais"),
        "fuzzy_sanchez": ("Composição max–min de Sanchez", "Peso parcial da observação; relação binária cadastrada"),
    }
    purpose, uncertainty = mechanisms.get(resultado.get("mecanismo"),
        ("Classificação supervisionada", resultado.get("politica_ausencia", "Conforme o artefato")))
    resultado["avaliacao"] = {
        "classificacao_sintomas": f"{len(resultado.get('sintomas_reconhecidos', []))} confirmados; {len(resultado.get('sintomas_incertos', []))} incertos",
        "confianca_diagnostica": "não estimada",
        "recomendacao_tratamento": "associações consultadas" if resultado.get("farmacos_relacionados") else "sem associações",
        "criterios_modelo": {
            "fase_mais_adequada": "classificação de hipóteses",
            "finalidade": purpose,
            "tratamento_incerteza": uncertainty,
            "interpretabilidade": "trilha de regras disponível" if resultado.get("mecanismo") == "regras_encadeadas" else "evidências de entrada disponíveis",
            "adequacao_clinica": "não avaliada",
        },
    }
