import re
from time import perf_counter
from pickle import UnpicklingError

from .clinical_input import extract_clinical_case
from .medications import select_medications
from .models import Doenca
from .presentation import _adicionar_graus_avaliacao
from .provenance import base_version
from .registry import DEFAULT_ENGINE, ModelUnavailable, engine_registry, model_status
from .utils import clinical_symptoms, normalize


CLINICAL_PROMPTS = {
    "temperatura_corporal_c": "Você mediu a temperatura corporal? Informe o valor em °C ou diga que não foi medida.",
    "idade_dias": "Qual é a idade do animal? Pode informar em dias, semanas, meses ou anos.",
    "fase_reprodutiva": "Em qual fase ele está: maternidade, creche, crescimento, terminação, matriz ou reprodução?",
    "duracao_horas": "Há quanto tempo os sinais começaram? Informe horas ou dias.",
    "temperatura_ambiente_c": "Qual é a temperatura do ambiente ou galpão, em °C? Se não souber, pode continuar com outros dados.",
    "genero": "É macho inteiro, macho castrado ou fêmea?",
    "tipo_suino": "Qual é o tipo de suíno: leitão, leitoa, matriz ou reprodutor?",
    "animais_afetados": "Quantos animais apresentam esses sinais?",
    "peso_kg": "Qual é o peso aproximado do animal, em kg?",
}


def clinical_data_text(data):
    templates = {
        "temperatura_corporal_c": "Temperatura corporal: {} °C",
        "temperatura_ambiente_c": "Temperatura ambiente: {} °C",
        "idade_dias": "Idade: {} dias", "fase_reprodutiva": "Fase: {}",
        "genero": "Sexo: {}", "estado_reprodutivo": "Estado reprodutivo: {}",
        "tipo_suino": "Tipo de suíno: {}", "duracao_horas": "Duração dos sintomas: {} horas",
        "peso_kg": "Peso: {} kg", "animais_afetados": "{} animais afetados",
    }
    return "; ".join(templates[key].format(value) for key, value in data.items())


def compose_text(data):
    answer = data["texto"]
    previous = data.get("pergunta_anterior", {})
    field = previous.get("campo", "sintoma" if data.get("sintoma_perguntado") else "")
    symptom = previous.get("sintoma") or data.get("sintoma_perguntado", "")
    normalized = normalize(answer)
    unknown = bool(re.match(r"^(?:nao sei|nao medi|nao foi|desconhe|nao tenho|sem medida|nao lembro)", normalized))
    if symptom and field == "sintoma":
        if unknown or re.match(r"^(?:talvez|nao tenho certeza)", normalized):
            answer = f"Talvez {symptom}. {answer}"
        elif re.match(r"^(?:nao|negativo|ausente)(?:\b|[,.])", normalized):
            answer = f"não apresenta {symptom}. {answer}"
        elif re.match(r"^(?:sim|positivo)(?:\b|[,.])", normalized):
            answer = f"apresenta {symptom}. {answer}"
    elif not unknown and field in CLINICAL_PROMPTS:
        short_value = re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:°?\s*c|graus|dias?|semanas?|mes(?:es)?|anos?|horas?|h|kg)?[.!]?", normalized)
        if short_value:
            number = re.search(r"\d+(?:[.,]\d+)?", normalized).group().replace(",", ".")
            units = bool(re.search(r"dias?|semanas?|mes(?:es)?|anos?|horas?|\bh\b", normalized))
            value = answer.rstrip(".!")
            if field == "idade_dias":
                answer = f"Idade: {value if units else number + ' dias'}"
            elif field == "duracao_horas":
                answer = f"Duração dos sintomas: {value if units else number + ' horas'}"
            elif field in {"temperatura_corporal_c", "temperatura_ambiente_c", "peso_kg", "animais_afetados"}:
                answer = clinical_data_text({field: number})
    parts = [data["contexto_clinico"], answer, clinical_data_text(data.get("dados_clinicos", {}))]
    return "\n".join(part for part in parts if part).strip()


def next_question(result, asked):
    variables = result["variaveis_reconhecidas"]
    if not result["sintomas_reconhecidos"] and "sintomas" not in asked:
        return {"campo": "sintomas", "sintoma": "", "texto": "Quais alterações você observou no animal? Descreva respiração, apetite, fezes, comportamento ou outros sinais."}
    for field, prompt in CLINICAL_PROMPTS.items():
        known = variables.get(field) not in (None, "")
        if field == "idade_dias" and variables.get("idade_categoria"):
            known = True
        if not known and field not in asked:
            return {"campo": field, "sintoma": "", "texto": prompt}
    hypotheses = result["hipoteses"]
    if len(hypotheses) < 2:
        return None
    diseases = Doenca.objects.filter(id__in=[item["id"] for item in hypotheses]).prefetch_related("sintomas")
    known = {normalize(name) for name in [*result["sintomas_reconhecidos"], *result["sintomas_negados"]]}
    candidates = {}
    for disease in diseases:
        for symptom in clinical_symptoms(disease):
            key = f"sintoma:{symptom.nome}"
            if normalize(symptom.nome) in known or key in asked:
                continue
            item = candidates.setdefault(symptom.nome, set())
            item.add(disease.id)
    eligible = [name for name, disease_ids in candidates.items() if 0 < len(disease_ids) < len(hypotheses)]
    if not eligible:
        return None
    symptom = min(eligible, key=lambda name: (-len(candidates[name]) * (len(hypotheses) - len(candidates[name])), name))
    return {"campo": "sintoma", "sintoma": symptom,
            "texto": f"O animal apresentou {symptom.lower()}? Pode responder sim, não ou que não tem certeza."}


def format_response(result, answer):
    variables = result["variaveis_reconhecidas"]
    labels = {"temperatura_corporal_c": "corporal (°C)", "temperatura_ambiente_c": "ambiente (°C)",
              "idade_dias": "idade em dias", "fase_reprodutiva": "fase", "tipo_suino": "tipo",
              "genero": "sexo", "estado_reprodutivo": "estado reprodutivo", "duracao_horas": "duração em horas",
              "peso_kg": "peso em kg", "animais_afetados": "animais afetados"}
    context = [f"{label}: {variables[key]}" for key, label in labels.items() if variables.get(key) not in (None, "")]
    blocks = ["Dados registrados: " + "; ".join(context) + "."] if context else []
    if variables.get("temperatura_ambiente_c") is not None:
        blocks.append("A temperatura ambiente fica registrada como contexto; esse campo não participa do classificador atual.")
    if result["sintomas_reconhecidos"]:
        blocks.append("Sinais confirmados: " + ", ".join(result["sintomas_reconhecidos"]) + ".")
    for key, label in [("sintomas_negados", "Sinais negados"), ("sintomas_incertos", "Sinais incertos")]:
        if result[key]:
            blocks.append(f"{label}: " + ", ".join(result[key]) + ".")
    hypotheses = result["hipoteses"]
    if hypotheses:
        blocks.append("Hipóteses atuais:\n" + "\n".join(
            f"{index}. {item['nome']} — sinais associados: {', '.join(item['evidencias']) or 'sem correspondência direta nos sinais relatados'}."
            for index, item in enumerate(hypotheses[:3], 1)))
        if not re.search(r"farmac|medic|tratamento|bulario", normalize(answer)):
            blocks.append("Você pode corrigir os dados, acrescentar observações ou pedir os fármacos associados às hipóteses.")
    else:
        blocks.append("Registrei o contexto. Ainda preciso de sinais reconhecidos para listar hipóteses; temperatura ambiente, idade e tipo também podem ser informados ao longo da conversa.")
    if re.search(r"farmac|medic|tratamento|bulario", normalize(answer)):
        medications = result["farmacos_relacionados"]
        blocks.append("Associações no bulário:\n" + "\n".join(
            f"• {item['nome_comercial']} ({item['principio_ativo'] or 'princípio ativo não informado'}): {', '.join(item['doencas_associadas'])}."
            for item in medications) if medications else "Não encontrei fármacos associados a estas hipóteses na base.")
        blocks.append("A associação não verifica adequação terapêutica, dose ou contraindicações individuais.")
    if result.get("alertas"):
        blocks.append("\n".join(result["alertas"]))
    question = result["pergunta_complementar"]
    blocks.append(question["texto"] if question else "Pode continuar com novas observações ou correções; recalcularei as hipóteses com o contexto atualizado.")
    blocks.append("Apoio à triagem; a decisão clínica cabe ao médico-veterinário.")
    return "\n\n".join(blocks)


def run_engine(case, key, require_trained=True):
    motor = engine_registry()[key].engine()
    if require_trained and hasattr(motor, "artifact_path"):
        try:
            artifact = motor._load_artifact()
        except (OSError, ValueError, EOFError, KeyError, ImportError, UnpicklingError) as error:
            raise ModelUnavailable() from error
        if artifact is None:
            raise ModelUnavailable()
        trained_base = artifact["metadata"].get("versao_base")
        if trained_base and trained_base != base_version():
            raise ModelUnavailable("O modelo foi treinado em outra versão da base. Gere os dados e retreine antes de usá-lo.")
    result = motor.inferir_caso(case, incluir_indicacoes=False)
    if hasattr(motor, "artifact_path"):
        artifact = motor._load_artifact()
        result["versao_modelo"] = artifact["metadata"].get("criado_em") if artifact else None
        result["versao_base_treino"] = artifact["metadata"].get("versao_base") if artifact else None
    result["farmacos_relacionados"] = select_medications(result["hipoteses"])
    _adicionar_graus_avaliacao(result)
    return result


def triage(data):
    text = compose_text(data)
    if len(text) > 28000:
        from rest_framework.exceptions import ValidationError
        raise ValidationError("O contexto atingiu o limite. Inicie uma nova triagem com o resumo do caso.")
    case = extract_clinical_case(text)
    result = run_engine(case, data.get("mecanismo", DEFAULT_ENGINE))
    asked = list(data.get("perguntas_realizadas", []))
    question = next_question(result, asked)
    if question:
        key = f"sintoma:{question['sintoma']}" if question["campo"] == "sintoma" else question["campo"]
        asked = list(dict.fromkeys([*asked, key]))
    result.update({"contexto_clinico": text, "pergunta_complementar": question, "perguntas_realizadas": asked,
                   "versao_base": base_version(),
                   "pipeline": {"entrada": "extrator_clinico_v4", "inferencia": result["mecanismo"],
                                "farmacos": "associacoes_relacionais", "versao": "triagem_v4"},
                   "contexto_apenas_registrado": ["temperatura_ambiente_c", "tipo_suino", "peso_kg", "animais_afetados"],
                   "aviso": "Resultados experimentais em base sintética; adequação clínica não estimada."})
    result["resposta"] = format_response(result, data["texto"])
    return result


def compare(text):
    case = extract_clinical_case(text)
    results = []
    for key in engine_registry():
        if key == DEFAULT_ENGINE:
            continue
        started = perf_counter()
        result = run_engine(case, key, require_trained=False)
        result["metricas_sistema"] = {
            "tempo_resposta_s": round(perf_counter() - started, 5),
            "sintomas_reconhecidos": len(result["sintomas_reconhecidos"]),
            "hipoteses_retornadas": len(result["hipoteses"]),
            "farmacos_retornados": len(result["farmacos_relacionados"]),
            "variaveis_reconhecidas": sum(value not in (None, "") for value in result["variaveis_reconhecidas"].values()),
        }
        results.append(result)
    first = [item["hipoteses"][0]["nome"] for item in results if item["hipoteses"]]
    return {"entrada": text, "resultados": results,
            "concordancia_top_1": len(first) == len(results) and len(set(first)) == 1,
            "observacao_metricas_preditivas": "Precisão, recall e acurácia exigem casos rotulados. O tempo mostrado mede classificação e consulta ao bulário após a extração compartilhada."}


def pipeline_status():
    return {"padrao": DEFAULT_ENGINE, "motores": [model_status(key) for key in engine_registry() if key != "machine_learning_k100"],
            "etapas": {"entrada": "Extrator clínico compartilhado", "inferencia": "Naive Bayes supervisionado",
                       "farmacos": "Consulta relacional às indicações cadastradas"}}
