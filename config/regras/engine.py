from bulario.clinical_input import context_adjustment, extract_clinical_case
from bulario.models import Doenca, Farmaco


class MotorRegras:
    """Inferência determinística baseada nas relações doença-sintoma da base."""

    nome = "regras"

    def inferir(self, texto, limite=5):
        caso = extract_clinical_case(texto)
        sintomas = caso["sintomas"]
        reconhecidos = {sintoma.id for sintoma in sintomas}
        hipoteses = []

        for doenca in Doenca.objects.prefetch_related("sintomas"):
            sintomas_doenca = list(doenca.sintomas.all())
            correspondentes = [item for item in sintomas_doenca if item.id in reconhecidos]
            if not correspondentes:
                continue
            cobertura = len(correspondentes) / max(len(sintomas_doenca), 1)
            precisao = len(correspondentes) / max(len(sintomas), 1)
            score_sintomas = (0.6 * cobertura) + (0.4 * precisao)
            score = max(0, min(1, score_sintomas + (0.25 * context_adjustment(doenca, caso))))
            hipoteses.append(self._hipotese(doenca, score, correspondentes))

        hipoteses.sort(key=lambda item: (-item["score"], item["nome"]))
        hipoteses = hipoteses[:limite]
        return self._resultado(caso, hipoteses)

    @staticmethod
    def _hipotese(doenca, score, evidencias):
        return {
            "id": doenca.id,
            "nome": doenca.nome,
            "tipo": doenca.tipo,
            "fase_comum": doenca.fase_comum,
            "score": round(score, 6),
            "evidencias": [item.nome for item in evidencias],
        }

    def _resultado(self, caso, hipoteses):
        ids = [item["id"] for item in hipoteses]
        farmacos = Farmaco.objects.filter(doencas_relacionadas__id__in=ids).distinct()[:3]
        return {
            "mecanismo": self.nome,
            "sintomas_reconhecidos": [item.nome for item in caso["sintomas"]],
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
