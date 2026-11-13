import re
from difflib import SequenceMatcher

from .models import Sintoma
from .utils import normalize, is_clinical_symptom


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
    r"(?:\bnao\b|\bsem\b|\bausencia\s+de\b|\bnunca\b)(?:\s+\w+|\s*,\s*){0,10}\s*$"
)
UNCERTAINTY_PATTERN = re.compile(r"(?:\bparece\b|\bparecendo\b|\btalvez\b|\bpode\s+estar\b|\bsuspeita\s+de\b)")


def _context_before(text, start, length=100):
    context = text[max(0, start - length):start]
    # Commas podem coordenar uma lista negada. Uma nova afirmação ou um
    # atributo seguido de "com" encerra o alcance do marcador anterior.
    context = re.split(
        r"[.;!?\n]|\b(?:mas|porem|agora|correcao)\b|"
        r",\s*(?=(?:apresenta|esta|tem|com|o|as)\b)|"
        r"\be\s+(?=esta\b|apresenta\b|tem\b|as\b|o\b)|"
        r"\b(?:gestante|prenha|lactante|vazia|macho|femea|castrado)\s+com\s+",
        context,
    )[-1]
    # A negação interna de um sinônimo positivo não nega os sinais seguintes.
    for aliases in SYMPTOM_ALIASES.values():
        for phrase in aliases:
            if phrase.startswith(("sem ", "nao ")):
                context = context.replace(phrase, "sinal observado")
    return re.sub(r"\bnao\s+(?:apenas|somente|so)\b", "", context)


def _is_negated(text, start):
    return bool(NEGATION_PATTERN.search(_context_before(text, start)))


def _is_uncertain(text, start):
    return bool(UNCERTAINTY_PATTERN.search(_context_before(text, start)))


def _find_symptoms(normalized_text):
    words = list(re.finditer(r"\b\w+\b", normalized_text))
    found = []
    negated = []
    uncertain = []
    symptoms = [s for s in Sintoma.objects.prefetch_related("doencas") if is_clinical_symptom(s.nome)]
    exact_mentions = []
    matches_by_id = {}
    for symptom in symptoms:
        target = normalize(symptom.nome)
        aliases = SYMPTOM_ALIASES.get(target, [])
        matches = []
        for phrase in [target, *aliases]:
            # Um hífen do nome cadastrado pode ser relatado como espaço.
            escaped = re.escape(phrase).replace(r"\-", r"[-\s]")
            matches.extend(re.finditer(rf"(?<!\w){escaped}(?!\w)", normalized_text))
        matches_by_id[symptom.id] = matches
        exact_mentions.extend((symptom.id, match) for match in matches)
    for symptom in symptoms:
        target = normalize(symptom.nome)
        matches = matches_by_id[symptom.id]
        had_exact = bool(matches)
        # "Sem febre alta" refere-se ao sinal específico e não apaga uma
        # menção independente a "febre". A base não contém uma ontologia
        # que autorize propagar estados entre sinais distintos.
        matches = [match for match in matches if not any(
            other_id != symptom.id and other.start() <= match.start() and other.end() >= match.end()
            and (other.start(), other.end()) != (match.start(), match.end())
            for other_id, other in exact_mentions)]
        if not matches and not had_exact and len(target) >= 5:
            size = len(re.findall(r"\w+", target))
            for index in range(len(words) - size + 1):
                start, end = words[index].start(), words[index + size - 1].end()
                candidate = normalized_text[start:end]
                if not re.search(r"[.;,!?\n]", candidate) and SequenceMatcher(None, target, candidate).ratio() >= 0.84:
                    matches.append(words[index])
        if not matches:
            continue
        # A última menção atualiza o estado; o início da expressão mantém
        # "sem apetite" positivo, mas permite "não está tossindo" negativo.
        match = max(matches, key=lambda item: (item.start(), item.end()))
        if _is_negated(normalized_text, match.start()):
            negated.append(symptom.nome)
        elif _is_uncertain(normalized_text, match.start()):
            uncertain.append(symptom.nome)
        else:
            found.append(symptom)
    return found, sorted(set(negated)), sorted(set(uncertain))


def _temperature(text, environmental=False):
    matches = []
    for match in re.finditer(r"(?<![\d.,])(-?\d{1,3}(?:[.,]\d+)?)(?!\d|[.,]\d)", text):
        before = text[max(0, match.start() - 70):match.start()]
        after = text[match.end():]
        if _is_negated(text, match.start()) or _is_uncertain(text, match.start()):
            continue
        cues = list(re.finditer(r"\b(?:ambiente|ambiental|galpao|instalacao|corporal|retal|febre)\b", before))
        is_environmental = bool(cues and cues[-1].group() in {"ambiente", "ambiental", "galpao", "instalacao"})
        if is_environmental != environmental:
            continue
        if re.match(r"\s*(?:dias?\b|horas?\b|h\b|kg\b|meses?\b)", after):
            continue
        unit = re.match(r"\s*(?:°(?:\s*c\b)?|c\b|graus\b)", after)
        cue = re.search(r"\b(?:temperatura(?:\s+(?:corporal|ambiente|ambiental))?|corporal|retal|ambiente|galpao|febre(?:\s+alta)?)\s*(?:de|a|em|esta|:|=)?\s*$", before)
        if unit or cue:
            matches.append(match)
    for match in reversed(matches):
        value = float(match.group(1).replace(",", "."))
        if environmental and -30 <= value <= 60:
            return value, ""
        if not environmental and 30 <= value <= 45:
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


def _age(text):
    units = r"(?:dias?|semanas?|mes(?:es)?|anos?)"
    pattern = rf"\b(?:idade\s*(?:de|:)?\s*(\d+)\s*({units})|(\d+)\s*({units})\s*(?:de\s*)?(?:idade|vida)|(?:leitao|suino|porco|animal)\s+de\s+(\d+)\s*({units}))\b"
    matches = list(re.finditer(pattern, text))
    if not matches:
        adult = list(re.finditer(r"\badulto\b", text))
        confirmed = adult and not _is_negated(text, adult[-1].start()) and not _is_uncertain(text, adult[-1].start())
        return None, ">180 dias" if confirmed else "", []
    if _is_negated(text, matches[-1].start()) or _is_uncertain(text, matches[-1].start()):
        return None, "", [match.span() for match in matches]
    number, unit = [value for value in matches[-1].groups() if value is not None]
    multiplier = 7 if unit.startswith("semana") else 30 if unit.startswith("mes") else 365 if unit.startswith("ano") else 1
    age = int(number) * multiplier
    category = ("<7 dias" if age < 7 else "7–21 dias" if age <= 21 else
                "22–70 dias" if age <= 70 else "71–180 dias" if age <= 180 else ">180 dias")
    return age, category, [match.span() for match in matches]


def _last_attribute(text, aliases):
    mentions = [(match, label) for phrase, label in aliases
                for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)]
    if not mentions:
        return "", "", ""
    match, label = max(mentions, key=lambda item: (item[0].start(), item[0].end()))
    if _is_negated(text, match.start()):
        return "", label, ""
    if _is_uncertain(text, match.start()):
        return "", "", label
    return label, "", ""


def extract_clinical_case(text):
    normalized = "\n".join(normalize(line) for line in text.splitlines())
    symptoms, negated, uncertain = _find_symptoms(normalized)
    temperature, temperature_category = _temperature(normalized)
    environmental_temperature, _ = _temperature(normalized, environmental=True)
    alerts = []
    age, age_category, age_spans = _age(normalized)

    if temperature_category in {"febre", "febre alta"}:
        temperature_symptoms = list(Sintoma.objects.filter(nome__icontains="Febre"))
        symptoms = [item for item in symptoms if "febre" not in normalize(item.nome)]
        wanted = {"febre", temperature_category}
        symptoms.extend(item for item in temperature_symptoms if normalize(item.nome) in wanted)
        negated = [name for name in negated if "febre" not in normalize(name)]
        uncertain = [name for name in uncertain if "febre" not in normalize(name)]
    elif temperature_category == "normal" and (
            any("febre" in normalize(item.nome) for item in symptoms)
            or any("febre" in normalize(name) for name in uncertain)):
        symptoms = [item for item in symptoms if "febre" not in normalize(item.nome)]
        uncertain = [name for name in uncertain if "febre" not in normalize(name)]
        alerts.append("A temperatura informada está na faixa normal e não confirma febre.")

    attributes = {
        "fase_reprodutiva": _last_attribute(normalized, list(PHASE_ALIASES.items())),
        "genero": _last_attribute(normalized, [("macho", "Macho inteiro"),
                    ("macho castrado", "Macho castrado"), ("femea", "Fêmea")]),
        "estado_reprodutivo": _last_attribute(normalized, [("gestante", "Gestante"),
                    ("prenha", "Gestante"), ("lactante", "Lactante"), ("vazia", "Vazia"),
                    ("nao aplicavel", "Não aplicável")]),
    }
    duration_matches = [match for match in re.finditer(r"\b(\d+)\s*(h|hora|horas|d|dia|dias)\b", normalized)
                        if not any(start <= match.start() < end for start, end in age_spans)]
    duration_match = duration_matches[-1] if duration_matches else None
    if duration_match and (_is_negated(normalized, duration_match.start()) or _is_uncertain(normalized, duration_match.start())):
        duration_match = None
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
        "temperatura_ambiente_c": environmental_temperature,
        "classificacao_temperatura": temperature_category,
        **{key: value[0] for key, value in attributes.items()},
        "idade_dias": age,
        "idade_categoria": age_category,
        "duracao_horas": duration_hours,
        "duracao_categoria": duration_category,
        "tipo_suino": _last_attribute(normalized, [
            ("leitao", "Leitão maternidade"), ("matriz", "Matriz"), ("reprodutor", "Reprodutor"),
            ("leitoa", "Leitoa"), ("cachaco", "Cachaço"),
            ("porca", "Matriz"), ("marrã", "Leitoa"), ("marra", "Leitoa"),
        ])[0],
        "peso_kg": _last_number(normalized, r"\b(?:peso\s*[:=]?\s*)?(\d+(?:[.,]\d+)?)\s*kg\b"),
        "animais_afetados": _last_number(normalized, r"\b(\d+)\s*(?:animais|suinos|porcos|leitoes)\s*(?:afetados|doentes|com sinais)\b"),
    }
    if negated:
        alerts.append(f"Sintomas explicitamente negados: {', '.join(negated)}.")
    if uncertain:
        alerts.append(f"Sintomas descritos com incerteza: {', '.join(uncertain)}.")
    return {
        "texto": text,
        "sintomas": unique_symptoms,
        "sintomas_negados": negated,
        "sintomas_incertos": uncertain,
        "variaveis": variables,
        "variaveis_negadas": {key: value[1] for key, value in attributes.items() if value[1]},
        "variaveis_incertas": {key: value[2] for key, value in attributes.items() if value[2]},
        "alertas": alerts,
    }


def _last_number(text, pattern):
    matches = list(re.finditer(pattern, text))
    if not matches or _is_negated(text, matches[-1].start()) or _is_uncertain(text, matches[-1].start()):
        return None
    return float(matches[-1].group(1).replace(",", "."))


def context_adjustment(disease, clinical_case):
    """Acumula as regras clínicas R1--R6 e limita o ajuste a [-1, 1].

    Os valores são heurísticos. O ajuste modifica a pontuação, sem excluir
    candidatas nem produzir novos fatos para encadeamento.
    """
    phase_text = normalize(disease.fase_comum)
    variables = clinical_case["variaveis"]
    adjustment = 0.0
    phase = normalize(variables["fase_reprodutiva"])
    if phase and phase_text and "nao informado" not in phase_text:
        if "todas as fases" in phase_text or phase in phase_text:
            # R1: fase correspondente ou enfermidade de todas as fases.
            adjustment += 0.6
        elif phase == "terminacao" and "crescimento" in phase_text:
            # R2: compatibilidade parcial entre terminação e crescimento.
            adjustment += 0.35
        else:
            # R3: descrição de fase sem correspondência reconhecida.
            adjustment -= 0.35
    pregnancy_only = "gestacao" in phase_text or "gestante" in phase_text
    if pregnancy_only:
        if variables["estado_reprodutivo"] == "Gestante":
            # R4: enfermidade gestacional e caso reconhecido como gestante.
            adjustment += 0.4
        elif variables["genero"].startswith("Macho"):
            # R5: enfermidade gestacional e caso reconhecido como macho.
            adjustment -= 0.65
    adjustment += negative_evidence_adjustment(disease, clinical_case)
    return max(-1.0, min(1.0, adjustment))


def negative_evidence_adjustment(disease, clinical_case):
    """R6: penaliza 0,4 por sintoma negado associado, até 0,8."""
    negated = {normalize(name) for name in clinical_case.get("sintomas_negados", [])}
    if not negated:
        return 0.0
    disease_symptoms = {normalize(item.nome) for item in disease.sintomas.all()}
    conflicts = len(negated & disease_symptoms)
    return -min(0.8, 0.4 * conflicts)
