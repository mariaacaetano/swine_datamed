import re
from difflib import SequenceMatcher

from .models import Sintoma
from .utils import normalize


PHASE_ALIASES = {
    "maternidade": "Leitão maternidade",
    "leitao": "Leitão maternidade",
    "creche": "Creche",
    "crescimento": "Crescimento",
    "terminacao": "Terminação",
    "matriz": "Matriz",
    "reprodutor": "Reprodutor",
}

SYMPTOM_ALIASES = {
    "perda de apetite": ["parou de comer", "nao quis a racao", "nao quer comer", "sem apetite"],
    "dispneia": ["respirando pesado", "dificuldade para respirar", "puxando o ar", "falta de ar"],
    "apatia": ["muito caido", "meio caido", "meio caidinho", "caidinho", "sem energia", "muito quieto"],
    "prostracao": ["nao levanta", "fica deitado", "so fica deitado"],
    "diarreia aquosa": ["fezes aguadas", "fezes bem aguadas", "fezes ficaram bem aguadas",
                         "fezes liquidas", "fezes como agua"],
    "claudicacao": ["mancando", "com mancada", "anda mancando"],
    "cianose": ["ficou roxo", "pele roxa", "extremidades roxas"],
    "coceira intensa": ["se cocando muito", "cocando bastante", "coceira forte"],
    "vomito": ["vomitou", "vomitando", "colocou a comida para fora"],
    "tosse": ["tossindo", "comecou a tossir"],
    "tremores": ["tremendo", "esta tremendo"],
    "convulsoes": ["convulsionando", "teve convulsao"],
    "perda de peso": ["emagrecendo", "perdeu peso"],
}

NEGATION_PATTERN = re.compile(
    r"(?:\bnao\b|\bsem\b|\bausencia\s+de\b|\bnunca\b)(?:\s+\w+){0,3}\s*$"
)
UNCERTAINTY_PATTERN = re.compile(r"(?:\bparece\b|\bparecendo\b|\btalvez\b|\bpode\s+estar\b|\bsuspeita\s+de\b)")


def _context_before(text, start, length=35):
    return text[max(0, start - length) : start]


def _is_negated(text, start):
    return bool(NEGATION_PATTERN.search(_context_before(text, start)))


def _is_uncertain(text, start):
    return bool(UNCERTAINTY_PATTERN.search(_context_before(text, start)))


def _find_symptoms(normalized_text):
    words = normalized_text.split()
    found = []
    negated = []
    uncertain = []
    for symptom in Sintoma.objects.prefetch_related("doencas"):
        target = normalize(symptom.nome)
        aliases = SYMPTOM_ALIASES.get(target, [])
        matched = False
        for phrase in [target, *aliases]:
            match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized_text)
            if not match:
                continue
            # Algumas expressões, como "sem apetite", já representam um sinal positivo.
            semantic_alias = phrase in aliases
            if not semantic_alias and _is_negated(normalized_text, match.start()):
                negated.append(symptom.nome)
                matched = True
                break
            found.append(symptom)
            if _is_uncertain(normalized_text, match.start()):
                uncertain.append(symptom.nome)
            matched = True
            break
        if matched:
            continue
        target_words = target.split()
        if len(target) < 5:
            continue
        for index in range(max(0, len(words) - len(target_words) + 1)):
            candidate = " ".join(words[index : index + len(target_words)])
            if SequenceMatcher(None, target, candidate).ratio() < 0.84:
                continue
            start = normalized_text.find(candidate)
            if _is_negated(normalized_text, start):
                negated.append(symptom.nome)
            else:
                found.append(symptom)
                if _is_uncertain(normalized_text, start):
                    uncertain.append(symptom.nome)
            break
    return found, sorted(set(negated)), sorted(set(uncertain))


def _temperature(text):
    values = re.findall(r"(?<!\d)(\d{2}(?:[.,]\d)?)(?:\s*°?\s*c)?(?!\d)", text)
    for raw in values:
        value = float(raw.replace(",", "."))
        if 30 <= value <= 45:
            if value < 37:
                category = "hipotermia"
            elif value <= 39.5:
                category = "normal"
            elif value <= 40:
                category = "febre"
            else:
                category = "febre alta"
            return value, category
    return None, ""


def extract_clinical_case(text):
    normalized = normalize(text)
    symptoms, negated, uncertain = _find_symptoms(normalized)
    temperature, temperature_category = _temperature(normalized)
    alerts = []

    if temperature_category in {"febre", "febre alta"}:
        temperature_symptoms = list(Sintoma.objects.filter(nome__icontains="Febre"))
        symptoms = [item for item in symptoms if "febre" not in normalize(item.nome)]
        wanted = {"febre", temperature_category}
        symptoms.extend(item for item in temperature_symptoms if normalize(item.nome) in wanted)
    elif temperature_category == "normal" and any("febre" in normalize(item.nome) for item in symptoms):
        symptoms = [item for item in symptoms if "febre" not in normalize(item.nome)]
        alerts.append("A temperatura informada está na faixa normal e não confirma febre.")

    phase = next((label for alias, label in PHASE_ALIASES.items() if alias in normalized), "")
    if "macho castrado" in normalized:
        gender = "Macho castrado"
    elif "macho" in normalized:
        gender = "Macho inteiro"
    elif "femea" in normalized:
        gender = "Fêmea"
    else:
        gender = ""
    reproductive_state = next(
        (label for alias, label in [("gestante", "Gestante"), ("prenha", "Gestante"),
                                    ("lactante", "Lactante"), ("vazia", "Vazia")] if alias in normalized),
        "",
    )
    duration_match = re.search(r"\b(\d+)\s*(h|hora|horas|d|dia|dias)\b", normalized)
    duration_hours = None
    if duration_match:
        duration_hours = int(duration_match.group(1))
        if duration_match.group(2).startswith("d"):
            duration_hours *= 24
    if duration_hours is None:
        duration_category = ""
    elif duration_hours < 24:
        duration_category = "<24h"
    elif duration_hours <= 72:
        duration_category = "1–3 dias"
    elif duration_hours <= 168:
        duration_category = "4–7 dias"
    else:
        duration_category = ">7 dias"

    unique_symptoms = list({item.id: item for item in symptoms}.values())
    variables = {
        "temperatura_corporal_c": temperature,
        "classificacao_temperatura": temperature_category,
        "fase_reprodutiva": phase,
        "genero": gender,
        "estado_reprodutivo": reproductive_state,
        "idade_categoria": "Adulto" if "adulto" in normalized else "",
        "duracao_horas": duration_hours,
        "duracao_categoria": duration_category,
    }
    if negated:
        alerts.append(f"Sintomas negados e desconsiderados: {', '.join(negated)}.")
    if uncertain:
        alerts.append(f"Sintomas descritos com incerteza: {', '.join(uncertain)}.")
    return {
        "texto": text,
        "sintomas": unique_symptoms,
        "sintomas_negados": negated,
        "sintomas_incertos": uncertain,
        "variaveis": variables,
        "alertas": alerts,
    }


def context_adjustment(disease, clinical_case):
    """Retorna ajuste entre -1 e 1 para fase e restrições reprodutivas."""
    phase_text = normalize(disease.fase_comum)
    variables = clinical_case["variaveis"]
    adjustment = 0.0
    phase = normalize(variables["fase_reprodutiva"])
    if phase and phase_text and "nao informado" not in phase_text:
        if "todas as fases" in phase_text or phase in phase_text:
            adjustment += 0.6
        elif phase == "terminacao" and "crescimento" in phase_text:
            adjustment += 0.35
        else:
            adjustment -= 0.35
    pregnancy_only = "gestacao" in phase_text or "gestante" in phase_text
    if pregnancy_only:
        if variables["estado_reprodutivo"] == "Gestante":
            adjustment += 0.4
        elif variables["genero"].startswith("Macho"):
            adjustment -= 0.65
    adjustment += negative_evidence_adjustment(disease, clinical_case)
    return max(-1.0, min(1.0, adjustment))


def negative_evidence_adjustment(disease, clinical_case):
    negated = {normalize(name) for name in clinical_case.get("sintomas_negados", [])}
    if not negated:
        return 0.0
    disease_symptoms = {normalize(item.nome) for item in disease.sintomas.all()}
    conflicts = len(negated & disease_symptoms)
    return -min(0.8, 0.4 * conflicts)
