from rest_framework import serializers

from .models import CasoClinico, Doenca, Farmaco, GeracaoDataset, Sintoma, Vacina, Variavel
from .registry import DEFAULT_ENGINE, engine_registry


class ClinicalDataSerializer(serializers.Serializer):
    temperatura_corporal_c = serializers.FloatField(min_value=30, max_value=45, required=False)
    temperatura_ambiente_c = serializers.FloatField(min_value=-30, max_value=60, required=False)
    idade_dias = serializers.IntegerField(min_value=0, max_value=10000, required=False)
    fase_reprodutiva = serializers.ChoiceField(choices=["Leitão maternidade", "Creche", "Crescimento", "Terminação", "Matriz", "Reprodutor"], required=False)
    genero = serializers.ChoiceField(choices=["Macho inteiro", "Macho castrado", "Fêmea"], required=False)
    estado_reprodutivo = serializers.ChoiceField(choices=["Gestante", "Lactante", "Vazia", "Não aplicável"], required=False)
    tipo_suino = serializers.ChoiceField(choices=["Leitão maternidade", "Creche", "Crescimento", "Terminação", "Matriz", "Reprodutor", "Leitoa", "Cachaço"], required=False)
    duracao_horas = serializers.IntegerField(min_value=0, max_value=87600, required=False)
    peso_kg = serializers.FloatField(min_value=0, max_value=2000, required=False)
    animais_afetados = serializers.IntegerField(min_value=0, max_value=1000000, required=False)


class QuestionSerializer(serializers.Serializer):
    campo = serializers.ChoiceField(choices=[*ClinicalDataSerializer().fields, "sintoma", "sintomas"], required=False)
    sintoma = serializers.CharField(max_length=180, required=False, allow_blank=True)


class TriageInputSerializer(serializers.Serializer):
    texto = serializers.CharField(max_length=4000, allow_blank=True, default="")
    contexto_clinico = serializers.CharField(max_length=24000, allow_blank=True, default="")
    sintoma_perguntado = serializers.CharField(max_length=180, allow_blank=True, default="")
    pergunta_anterior = QuestionSerializer(required=False)
    perguntas_realizadas = serializers.ListField(child=serializers.CharField(max_length=200), max_length=100, default=list)
    dados_clinicos = ClinicalDataSerializer(required=False)
    mecanismo = serializers.ChoiceField(choices=[], default=DEFAULT_ENGINE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mecanismo"].choices = list(engine_registry())

    def validate(self, attrs):
        if not attrs.get("texto") and not attrs.get("dados_clinicos"):
            raise serializers.ValidationError("Informe um relato ou dados clínicos.")
        return attrs


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
