from rest_framework import serializers

from .models import CasoClinico, Doenca, Farmaco, GeracaoDataset, Sintoma, Vacina, Variavel


class SintomaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sintoma
        fields = ["id", "nome"]


class DoencaSerializer(serializers.ModelSerializer):
    sintomas = SintomaSerializer(many=True, read_only=True)

    class Meta:
        model = Doenca
        fields = ["id", "source_id", "nome", "tipo", "agente_etiologico", "fase_comum", "sintomas_texto", "sintomas"]


class VariavelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variavel
        fields = ["id", "nome", "descricao", "opcoes"]


class FarmacoSerializer(serializers.ModelSerializer):
    doencas_relacionadas = DoencaSerializer(many=True, read_only=True)

    class Meta:
        model = Farmaco
        fields = [
            "id",
            "nome_comercial",
            "principio_ativo",
            "classe",
            "indicacoes_principais",
            "posologia",
            "via_administracao",
            "carencia",
            "contraindicacoes",
            "reacoes_adversas",
            "mecanismo_acao",
            "precaucoes",
            "doencas_relacionadas",
        ]


class VacinaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vacina
        fields = "__all__"


class CasoClinicoSerializer(serializers.ModelSerializer):
    doenca = DoencaSerializer(read_only=True)

    class Meta:
        model = CasoClinico
        fields = ["id", "numero", "doenca", "sintomas", "variaveis"]


class GeracaoDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeracaoDataset
        fields = ["id", "total_registros", "semente", "arquivo", "resumo", "created_at"]
