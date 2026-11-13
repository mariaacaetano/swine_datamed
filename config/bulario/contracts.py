from .models import Farmaco


def inference_result(caso, hipoteses, mecanismo, incluir_indicacoes=True, **metadata):
    disease_ids = [item["id"] for item in hipoteses]
    medications = (Farmaco.objects.completos().filter(doencas_relacionadas__id__in=disease_ids).distinct()[:3]
                   if incluir_indicacoes else [])
    return {
        "mecanismo": mecanismo,
        "sintomas_reconhecidos": [item.nome for item in caso["sintomas"]],
        "sintomas_negados": caso["sintomas_negados"],
        "sintomas_incertos": caso["sintomas_incertos"],
        "variaveis_reconhecidas": caso["variaveis"],
        "variaveis_negadas": caso.get("variaveis_negadas", {}),
        "variaveis_incertas": caso.get("variaveis_incertas", {}),
        "alertas": caso["alertas"],
        "hipoteses": hipoteses,
        "farmacos_relacionados": [{"nome_comercial": item.nome_comercial,
                                   "principio_ativo": item.principio_ativo,
                                   "via_administracao": item.via_administracao,
                                   "carencia": item.carencia} for item in medications],
        **metadata,
    }
