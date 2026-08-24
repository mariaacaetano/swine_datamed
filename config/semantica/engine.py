from collections import defaultdict

from bulario.clinical_input import context_adjustment, extract_clinical_case
from bulario.models import Doenca, Farmaco


class MotorSemantico:
    """Percorre o grafo Sintoma -> Doença -> Fármaco mantido pelo ORM."""

    nome = "semantica"

    def inferir(self, texto, limite=5):
        caso = extract_clinical_case(texto)
        sintomas = caso["sintomas"]
        caminhos = defaultdict(list)
        for sintoma in sintomas:
            for doenca in sintoma.doencas.all():
                caminhos[doenca.id].append(sintoma.nome)

        doencas = {
            item.id: item
            for item in Doenca.objects.prefetch_related("sintomas").filter(id__in=caminhos)
        }
        hipoteses = []
        for doenca_id, evidencias in caminhos.items():
            doenca = doencas[doenca_id]
            total_doenca = doenca.sintomas.count()
            uniao = len(sintomas) + total_doenca - len(evidencias)
            similaridade = len(evidencias) / max(uniao, 1)
            score = max(0, min(1, similaridade + (0.25 * context_adjustment(doenca, caso))))
            hipoteses.append({
                "id": doenca.id,
                "nome": doenca.nome,
                "tipo": doenca.tipo,
                "fase_comum": doenca.fase_comum,
                "score": round(score, 6),
                "evidencias": evidencias,
                "caminhos_semanticos": [f"{nome} -> {doenca.nome}" for nome in evidencias],
            })

        hipoteses.sort(key=lambda item: (-item["score"], item["nome"]))
        hipoteses = hipoteses[:limite]
        ids = [item["id"] for item in hipoteses]
        farmacos = Farmaco.objects.filter(doencas_relacionadas__id__in=ids).distinct()[:3]
        return {
            "mecanismo": self.nome,
            "sintomas_reconhecidos": [item.nome for item in sintomas],
            "sintomas_negados": caso["sintomas_negados"],
            "sintomas_incertos": caso["sintomas_incertos"],
            "variaveis_reconhecidas": caso["variaveis"],
            "alertas": caso["alertas"],
            "hipoteses": hipoteses,
            "farmacos_relacionados": [
                {
                    "nome_comercial": item.nome_comercial,
                    "principio_ativo": item.principio_ativo,
                    "via_administracao": item.via_administracao,
                    "carencia": item.carencia,
                }
                for item in farmacos
            ],
        }
