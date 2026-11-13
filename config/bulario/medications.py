from .models import Farmaco, Indicacao
from .medication_quality import complete_medication_condition


def select_medications(hypotheses, limit=3):
    positions = {hypothesis["id"]: index for index, hypothesis in enumerate(hypotheses)}
    indications = Indicacao.objects.filter(
        complete_medication_condition("farmaco__"),
        doenca_id__in=positions, farmaco__isnull=False,
    ).select_related("doenca", "farmaco")
    candidates = {}
    for indication in indications:
        medication = indication.farmaco
        item = candidates.setdefault(medication.id, {
            "id": medication.id, "nome_comercial": medication.nome_comercial,
            "principio_ativo": medication.principio_ativo,
            "via_administracao": medication.via_administracao,
            "carencia": medication.carencia, "contraindicacoes": medication.contraindicacoes,
            "doencas_associadas": [], "evidencias_associacao": [],
            "ordem_hipotese": positions[indication.doenca_id], "prioridade_base": indication.prioridade,
        })
        item["ordem_hipotese"] = min(item["ordem_hipotese"], positions[indication.doenca_id])
        priorities = [value for value in [item["prioridade_base"], indication.prioridade] if value is not None]
        item["prioridade_base"] = min(priorities) if priorities else None
        if indication.doenca.nome not in item["doencas_associadas"]:
            item["doencas_associadas"].append(indication.doenca.nome)
        item["evidencias_associacao"].append({"indicacao_id": indication.id,
            "doenca": indication.doenca.nome, "tipo": indication.tipo, "prioridade": indication.prioridade})
    linked = Farmaco.objects.completos().filter(doencas_relacionadas__id__in=positions).prefetch_related("doencas_relacionadas").distinct()
    for medication in linked:
        if medication.id in candidates:
            continue
        related = [disease for disease in medication.doencas_relacionadas.all() if disease.id in positions]
        candidates[medication.id] = {
            "id": medication.id, "nome_comercial": medication.nome_comercial,
            "principio_ativo": medication.principio_ativo, "via_administracao": medication.via_administracao,
            "carencia": medication.carencia, "contraindicacoes": medication.contraindicacoes,
            "doencas_associadas": [disease.nome for disease in related],
            "evidencias_associacao": [], "ordem_hipotese": min(positions[disease.id] for disease in related),
            "prioridade_base": None,
        }
    ordered = sorted(candidates.values(), key=lambda item: (
        item["ordem_hipotese"], item["prioridade_base"] if item["prioridade_base"] is not None else 9999,
        item["nome_comercial"],
    ))
    return ordered[:limit]
