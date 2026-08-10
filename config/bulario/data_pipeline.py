import csv
import json
import random
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

from django.db import transaction

from .models import CasoClinico, Doenca, Farmaco, GeracaoDataset, Indicacao, Sintoma, Vacina, Variavel
from .utils import clean_text, is_filled, normalize, split_list


FILES = {
    "doencas": ("BaseDoencas.csv", "DOENÇA PADRONIZADA"),
    "variaveis": ("BaseVariaveis.csv", "Variável"),
    "farmacos": ("BularioFarmacos.csv", "Nome comercial"),
    "vacinas": ("BularioVacinas.csv", "Nome comercial"),
    "indicacoes": ("FarmacoDoenca.csv", "MEDICAMENTO"),
    "sintomas": ("SintomasDoencas.csv", "SINTOMA PADRONIZADO"),
}


def read_structured_csv(path, header_marker):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        raw = list(csv.reader(handle))
    header_index = next((i for i, row in enumerate(raw) if header_marker in row), None)
    if header_index is None:
        raise ValueError(f"Cabeçalho '{header_marker}' não encontrado em {path.name}.")
    header = [clean_text(item) for item in raw[header_index]]
    result = []
    for values in raw[header_index + 1 :]:
        row = {name: clean_text(values[i] if i < len(values) else "") for i, name in enumerate(header)}
        if any(is_filled(value) for value in row.values()):
            result.append(row)
    return result


def parse_options(value):
    text = clean_text(value)
    if not is_filled(text) or normalize(text) in {"numerico", "dias", "campo texto", "campo texto ou categorias"}:
        return []
    return [clean_text(item) for item in re.split(r"\s+/\s+", text) if is_filled(item)]


def _int(value):
    try:
        return int(clean_text(value))
    except (TypeError, ValueError):
        return None


def _best_disease(name, disease_map):
    key = normalize(re.sub(r"\s*\((?:preven[cç][aã]o)\)\s*$", "", name, flags=re.I))
    if key in disease_map:
        return disease_map[key]
    candidates = [(len(k), disease) for k, disease in disease_map.items() if len(k) >= 5 and (k in key or key in k)]
    return max(candidates, default=(0, None))[1]


@transaction.atomic
def import_base_data(base_dir, clear=False):
    base_dir = Path(base_dir)
    tables = {key: read_structured_csv(base_dir / filename, marker) for key, (filename, marker) in FILES.items()}
    if clear:
        CasoClinico.objects.all().delete()
        GeracaoDataset.objects.all().delete()
        Indicacao.objects.all().delete()
        Farmaco.objects.all().delete()
        Vacina.objects.all().delete()
        Doenca.objects.all().delete()
        Sintoma.objects.all().delete()
        Variavel.objects.all().delete()

    disease_map = {}
    for row in tables["doencas"]:
        name = row["DOENÇA PADRONIZADA"]
        if not is_filled(name):
            continue
        disease, _ = Doenca.objects.update_or_create(nome=name, defaults={
            "source_id": _int(row.get("ID")), "tipo": row.get("TIPO", ""),
            "agente_etiologico": row.get("AGENTE ETIOLÓGICO", ""),
            "fase_comum": row.get("FASE COMUM", ""), "sintomas_texto": row.get("SINTOMAS PADRONIZADOS", ""),
        })
        disease_map[normalize(name)] = disease
        for symptom_name in split_list(row.get("SINTOMAS PADRONIZADOS")):
            symptom, _ = Sintoma.objects.get_or_create(nome=symptom_name)
            disease.sintomas.add(symptom)

    for row in tables["sintomas"]:
        name = row["SINTOMA PADRONIZADO"]
        if not is_filled(name):
            continue
        symptom, _ = Sintoma.objects.get_or_create(nome=name)
        for disease_name in split_list(row.get("DOENÇAS ASSOCIADAS PADRONIZADAS")):
            disease = _best_disease(disease_name, disease_map)
            if disease:
                disease.sintomas.add(symptom)

    for row in tables["variaveis"]:
        name = row["Variável"]
        if is_filled(name):
            raw_options = row.get("Valores / Opções sugeridas", "")
            Variavel.objects.update_or_create(nome=name, defaults={"descricao": raw_options, "opcoes": parse_options(raw_options)})

    farmaco_map = {}
    farmaco_fields = {
        "principio_ativo": "Princípio ativo", "classe": "Classe", "indicacoes_principais": "Indicações principais",
        "posologia": "Posologia", "via_administracao": "Via administração", "carencia": "Carência",
        "contraindicacoes": "Contraindicações", "reacoes_adversas": "Reações adversas",
        "mecanismo_acao": "Mecanismo de ação", "precaucoes": "Precauções",
    }
    for row in tables["farmacos"]:
        name = row["Nome comercial"]
        if not is_filled(name):
            continue
        defaults = {field: (row.get(column, "") if is_filled(row.get(column, "")) else "") for field, column in farmaco_fields.items()}
        defaults["source_id"] = _int(row.get("ID"))
        item, _ = Farmaco.objects.update_or_create(nome_comercial=name, defaults=defaults)
        farmaco_map[normalize(name)] = item

    vacina_map = {}
    vaccine_fields = {
        "tipo": "Tipo", "doencas_prevenidas": "Doenças prevenidas", "agentes_alvo": "Agente(s)-alvo",
        "categoria": "Categoria", "fase_indicada": "Fase indicada", "idade_recomendada": "Idade recomendada",
        "dose": "Dose", "via": "Via", "numero_doses": "Número de doses", "intervalo_reforco": "Intervalo/Reforço",
        "inicio_imunidade": "Início da imunidade", "duracao_imunidade": "Duração da imunidade", "carencia": "Carência",
        "armazenamento": "Armazenamento", "contraindicacoes": "Contraindicações",
        "reacoes_adversas": "Reações adversas", "observacoes": "Observações",
    }
    for row in tables["vacinas"]:
        name = row["Nome comercial"]
        if not is_filled(name):
            continue
        defaults = {field: (row.get(column, "") if is_filled(row.get(column, "")) else "") for field, column in vaccine_fields.items()}
        defaults["source_id"] = _int(row.get("ID"))
        item, _ = Vacina.objects.update_or_create(nome_comercial=name, defaults=defaults)
        vacina_map[normalize(name)] = item

    Indicacao.objects.all().delete()
    for farmaco in Farmaco.objects.all():
        farmaco.doencas_relacionadas.clear()
    for row in tables["indicacoes"]:
        medication, indication = row["MEDICAMENTO"], row.get("DOENÇA/INDICAÇÃO PADRONIZADA", "")
        if not (is_filled(medication) and is_filled(indication)):
            continue
        farmaco, vacina = farmaco_map.get(normalize(medication)), vacina_map.get(normalize(medication))
        relation = Indicacao.objects.create(
            medicamento=medication, doenca_indicacao=indication, tipo=row.get("TIPO", ""),
            prioridade=_int(row.get("PRIORIDADE")), farmaco=farmaco, vacina=vacina,
            doenca=_best_disease(indication, disease_map),
        )
        if relation.farmaco and relation.doenca:
            relation.farmaco.doencas_relacionadas.add(relation.doenca)

    return {"doencas": Doenca.objects.count(), "sintomas": Sintoma.objects.count(), "variaveis": Variavel.objects.count(),
            "farmacos": Farmaco.objects.count(), "vacinas": Vacina.objects.count(), "indicacoes": Indicacao.objects.count()}


@transaction.atomic
def generate_dataset(output_path, total=None, seed=42, replace=True):
    """Gera todas as combinações não vazias de sintomas de cada doença.

    ``total`` é apenas um limite opcional mantido para compatibilidade. Sem limite,
    o dataset representa o espaço combinatório completo da base importada.
    """
    diseases = list(Doenca.objects.prefetch_related("sintomas").order_by("source_id", "nome"))
    all_symptoms = list(Sintoma.objects.order_by("nome").values_list("nome", flat=True))
    if not diseases or not all_symptoms:
        raise ValueError("Importe a base de dados antes de gerar o dataset.")
    if replace:
        GeracaoDataset.objects.all().delete()
    rows = []
    for disease in diseases:
        available = sorted({item.nome for item in disease.sintomas.all()}, key=normalize)
        for size in range(1, len(available) + 1):
            for selected in combinations(available, size):
                rows.append((disease, list(selected)))
    if total is not None:
        if total < len(diseases):
            raise ValueError("O limite deve permitir ao menos um caso por doença.")
        rows = rows[:total]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generation = GeracaoDataset.objects.create(total_registros=len(rows), semente=seed, arquivo=str(output_path))
    cases = [CasoClinico(geracao=generation, numero=i, doenca=disease, sintomas=symptoms, variaveis={})
             for i, (disease, symptoms) in enumerate(rows, 1)]
    CasoClinico.objects.bulk_create(cases, batch_size=500)
    symptom_columns = {name: f"sintoma_{i:03d}_{re.sub(r'[^a-z0-9]+', '_', normalize(name)).strip('_')}"
                       for i, name in enumerate(all_symptoms, 1)}
    headers = ["caso_id", "doenca", "tipo_doenca", "agente_etiologico", "fase_comum",
               "quantidade_sintomas", "sintomas_presentes", *symptom_columns.values()]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for case, (disease, symptoms) in zip(cases, rows):
            present = set(symptoms)
            writer.writerow({"caso_id": case.numero, "doenca": disease.nome, "tipo_doenca": disease.tipo,
                             "agente_etiologico": disease.agente_etiologico, "fase_comum": disease.fase_comum,
                             "quantidade_sintomas": len(symptoms), "sintomas_presentes": "; ".join(symptoms),
                             **{column: int(name in present) for name, column in symptom_columns.items()}})
    distribution = Counter(disease.nome for disease, _ in rows)
    generation.resumo = {"doencas": len(diseases), "sintomas": len(all_symptoms),
                         "combinacoes_exaustivas": total is None,
                         "min_por_doenca": min(distribution.values()), "max_por_doenca": max(distribution.values()),
                         "distribuicao": dict(sorted(distribution.items()))}
    generation.save(update_fields=["resumo", "updated_at"])
    return generation


def _choice(variable, rng, reported_probability=0.75):
    options = [item for item in variable.opcoes if normalize(item) != "nao informado"]
    if not options or rng.random() > reported_probability:
        return "Não informado"
    return rng.choice(options)


def _symptom_group(symptoms):
    text = normalize(" ".join(symptoms))
    groups = [
        ("Respiratório", ["tosse", "respir", "dispne", "nasal", "espir"]),
        ("Digestivo", ["diarre", "fezes", "vomit", "desidrat"]),
        ("Neurológico", ["tremor", "convuls", "coordena", "nervos", "desorient"]),
        ("Reprodutivo", ["aborto", "natimorto", "mumific", "reprod", "cio", "placenta"]),
        ("Dermatológico", ["pele", "cutan", "alopecia", "sarna", "coceira"]),
        ("Locomotor", ["claud", "articul", "andar", "mobilidade"]),
    ]
    return next((label for label, tokens in groups if any(token in text for token in tokens)), "Sistêmico")


def _phase_value(disease):
    phase = normalize(disease.fase_comum)
    mapping = [("maternidade", "Leitão maternidade"), ("creche", "Creche"),
               ("crescimento", "Crescimento"), ("terminacao", "Terminação"),
               ("matriz", "Matriz"), ("reprodutor", "Reprodutor")]
    return next((label for token, label in mapping if token in phase), "Não informado")


def _clinical_values(variables, disease, symptoms, rng):
    values = {variable.nome: _choice(variable, rng) for variable in variables}
    variable_by_key = {normalize(variable.nome): variable for variable in variables}
    by_key = {key: variable.nome for key, variable in variable_by_key.items()}
    symptom_text = normalize(" ".join(symptoms))

    def set_value(key, value):
        if key in by_key:
            values[by_key[key]] = value

    set_value("sintomas principais", "; ".join(symptoms))
    set_value("tipos de sintomas", _symptom_group(symptoms))
    set_value("fase reprodutiva", _phase_value(disease))
    set_value("diagnostico confirmado", disease.nome)
    set_value("suspeita clinica inicial", disease.nome if rng.random() < 0.7 else "Não informado")
    set_value("resultado laboratorial", f"Compatível com {disease.nome}" if rng.random() < 0.55 else "Não informado")

    if "febre" in symptom_text:
        set_value("temperatura corporal (°c)", rng.choice(["39,6–40,0 (febre)", ">40,0 (febre alta)"]))
    else:
        set_value("temperatura corporal (°c)", rng.choice(["37,0–39,5 (normal)", "Não informado"]))

    respiratory = any(token in symptom_text for token in ["tosse", "respir", "dispne", "ofegante"])
    set_value("frequencia respiratoria (mov/min)", rng.choice(["26–40", ">40"]) if respiratory else rng.choice(["15–25", "Não informado"]))

    reproductive = any(token in symptom_text for token in ["aborto", "natimorto", "mumific", "placenta", "cio", "agalaxia"])
    if reproductive:
        set_value("genero", "Fêmea")
        set_value("estado reprodutivo", rng.choice(["Gestante", "Lactante", "Vazia"]))
    else:
        set_value("estado reprodutivo", "Não aplicável")

    conditional = {
        "presenca de aborto": "Sim" if "aborto" in symptom_text else "Não informado",
        "natimortos / mumificados": "Sim" if any(t in symptom_text for t in ["natimorto", "mumific"]) else "Não informado",
        "secrecao nasal": rng.choice(["Serosa", "Purulenta"]) if "nasal" in symptom_text else "Não informado",
        "secrecao ocular": "Sim" if "ocular" in symptom_text else "Não informado",
        "lesoes cutaneas": "Sim" if any(t in symptom_text for t in ["pele", "cutan", "lesao"]) else "Não informado",
        "edema": "Sim" if "edema" in symptom_text else "Não informado",
    }
    for key, value in conditional.items():
        set_value(key, value)

    if "diarre" in symptom_text:
        diarrhea = "Hemorrágica" if any(t in symptom_text for t in ["hemorr", "sangue"]) else rng.choice(["Aquosa", "Pastosa"])
        set_value("tipo de diarreia", diarrhea)
    else:
        set_value("tipo de diarreia", "Não informado")

    # Variáveis ambientais são deliberadamente ausentes na maioria dos casos,
    # pois não podem ser inferidas a partir dos sintomas ou do diagnóstico.
    for key in ["temperatura do ambiente (°c)", "umidade ambiente (%)"]:
        if key in by_key:
            values[by_key[key]] = _choice(variable_by_key[key], rng, reported_probability=0.35)
    return values


@transaction.atomic
def generate_clinical_dataset(output_path, variations_per_combination=10, seed=42, replace=False):
    """Amostra observações clínicas finitas, preservando ausências como 'Não informado'."""
    if variations_per_combination < 1:
        raise ValueError("O número de observações por combinação deve ser positivo.")
    diseases = list(Doenca.objects.prefetch_related("sintomas").order_by("source_id", "nome"))
    variables = list(Variavel.objects.order_by("id"))
    all_symptoms = list(Sintoma.objects.order_by("nome").values_list("nome", flat=True))
    if not diseases or not variables:
        raise ValueError("Importe a base de dados antes de gerar o dataset clínico.")
    if replace:
        GeracaoDataset.objects.all().delete()
    rng = random.Random(seed)
    base_rows = []
    for disease in diseases:
        symptoms = sorted({item.nome for item in disease.sintomas.all()}, key=normalize)
        for size in range(1, len(symptoms) + 1):
            base_rows.extend((disease, list(selected)) for selected in combinations(symptoms, size))

    total = len(base_rows) * variations_per_combination
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generation = GeracaoDataset.objects.create(total_registros=total, semente=seed, arquivo=str(output_path))
    symptom_columns = {name: f"sintoma_{i:03d}_{re.sub(r'[^a-z0-9]+', '_', normalize(name)).strip('_')}"
                       for i, name in enumerate(all_symptoms, 1)}
    headers = ["observacao_id", "combinacao_id", "variacao", "doenca", "tipo_doenca", "agente_etiologico",
               "fase_comum", "quantidade_sintomas", "sintomas_presentes", *symptom_columns.values(),
               *[variable.nome for variable in variables]]
    cases = []
    number = 0
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for combination_id, (disease, symptoms) in enumerate(base_rows, 1):
            present = set(symptoms)
            for variation in range(1, variations_per_combination + 1):
                number += 1
                values = _clinical_values(variables, disease, symptoms, rng)
                cases.append(CasoClinico(geracao=generation, numero=number, doenca=disease,
                                         sintomas=symptoms, variaveis=values))
                writer.writerow({"observacao_id": number, "combinacao_id": combination_id, "variacao": variation,
                                 "doenca": disease.nome, "tipo_doenca": disease.tipo,
                                 "agente_etiologico": disease.agente_etiologico, "fase_comum": disease.fase_comum,
                                 "quantidade_sintomas": len(symptoms), "sintomas_presentes": "; ".join(symptoms),
                                 **{column: int(name in present) for name, column in symptom_columns.items()}, **values})
                if len(cases) == 500:
                    CasoClinico.objects.bulk_create(cases, batch_size=500)
                    cases.clear()
        if cases:
            CasoClinico.objects.bulk_create(cases, batch_size=500)
    generation.resumo = {"tipo": "clinico_sintetico", "combinacoes_base": len(base_rows),
                         "variacoes_por_combinacao": variations_per_combination, "variaveis": len(variables),
                         "sintomas": len(all_symptoms), "ausencia": "Não informado",
                         "faixas_experimentais_pendentes_validacao_veterinaria": True}
    generation.save(update_fields=["resumo", "updated_at"])
    return generation


ML_EXCLUDED_VARIABLES = {
    "sintomas principais",
    "suspeita clinica inicial",
    "diagnostico confirmado",
    "resultado laboratorial",
}


def _stratified_combination_split(base_rows, rng):
    """Separa combinações dentro de cada doença e mantém todas as classes no treino."""
    by_disease = {}
    for row in base_rows:
        by_disease.setdefault(row[0].id, []).append(row)
    assigned = {"treino": [], "validacao": [], "teste": []}
    for rows in by_disease.values():
        rng.shuffle(rows)
        count = len(rows)
        if count == 1:
            assigned["treino"].extend(rows)
            continue
        if count == 2:
            assigned["treino"].append(rows[0])
            assigned["teste"].append(rows[1])
            continue
        validation_count = max(1, round(count * 0.15))
        test_count = max(1, round(count * 0.15))
        train_count = count - validation_count - test_count
        if train_count < 1:
            train_count, validation_count, test_count = 1, 1, count - 2
        assigned["treino"].extend(rows[:train_count])
        assigned["validacao"].extend(rows[train_count : train_count + validation_count])
        assigned["teste"].extend(rows[train_count + validation_count :])
    return assigned


def generate_ml_dataset(output_dir, variations_per_combination=96, seed=42):
    """Gera arquivos para ML sem atributos derivados diretamente do diagnóstico."""
    if variations_per_combination < 1:
        raise ValueError("O número de variações para machine learning deve ser positivo.")
    diseases = list(Doenca.objects.prefetch_related("sintomas").order_by("source_id", "nome"))
    variables = [item for item in Variavel.objects.order_by("id") if normalize(item.nome) not in ML_EXCLUDED_VARIABLES]
    all_symptoms = list(Sintoma.objects.order_by("nome").values_list("nome", flat=True))
    if not diseases or not variables:
        raise ValueError("Importe a base de dados antes de gerar o dataset de machine learning.")
    base_rows = []
    combination_id = 0
    for disease in diseases:
        symptoms = sorted({item.nome for item in disease.sintomas.all()}, key=normalize)
        for size in range(1, len(symptoms) + 1):
            for selected in combinations(symptoms, size):
                combination_id += 1
                base_rows.append((disease, list(selected), combination_id))

    rng = random.Random(seed)
    split_rows = _stratified_combination_split(base_rows, rng)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    symptom_columns = {name: f"sintoma_{i:03d}_{re.sub(r'[^a-z0-9]+', '_', normalize(name)).strip('_')}"
                       for i, name in enumerate(all_symptoms, 1)}
    headers = ["observacao_id", "combinacao_id", *symptom_columns.values(),
               *[variable.nome for variable in variables], "doenca_alvo"]
    counts, combination_counts = {}, {}
    observation_id = 0
    for split, rows in split_rows.items():
        path = output_dir / f"{split}.csv"
        combination_counts[split] = len(rows)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            written = 0
            for disease, symptoms, base_id in rows:
                present = set(symptoms)
                for _ in range(variations_per_combination):
                    observation_id += 1
                    values = _clinical_values(variables, disease, symptoms, rng)
                    writer.writerow({"observacao_id": observation_id, "combinacao_id": base_id,
                                     **{column: int(name in present) for name, column in symptom_columns.items()},
                                     **values, "doenca_alvo": disease.nome})
                    written += 1
            counts[split] = written

    total = sum(counts.values())
    summary = {"tipo": "machine_learning", "total": total, "semente": seed,
               "variacoes_por_combinacao": variations_per_combination,
               "combinacoes": combination_counts, "registros": counts,
               "atributos_sintomas": len(all_symptoms), "atributos_clinicos": len(variables),
               "campos_excluidos_por_vazamento": sorted(ML_EXCLUDED_VARIABLES),
               "divisao_antes_da_geracao_das_variacoes": True,
               "observacao": "Classes com uma única combinação aparecem somente no treino."}
    with (output_dir / "metadados.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    GeracaoDataset.objects.create(total_registros=total, semente=seed, arquivo=str(output_dir), resumo=summary)
    return summary
