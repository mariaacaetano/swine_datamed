import hashlib
import json

from .models import Doenca, Indicacao


def base_version():
    diseases = [{"nome": disease.nome, "tipo": disease.tipo, "fase": disease.fase_comum,
                 "sintomas": sorted(symptom.nome for symptom in disease.sintomas.all())}
                for disease in Doenca.objects.prefetch_related("sintomas").order_by("nome")]
    indications = list(Indicacao.objects.order_by("medicamento", "doenca_indicacao", "tipo").values_list(
        "medicamento", "doenca_indicacao", "tipo", "prioridade"))
    encoded = json.dumps({"doencas": diseases, "indicacoes": indications}, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
