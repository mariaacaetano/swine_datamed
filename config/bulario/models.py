from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Sintoma(TimeStampedModel):
    nome = models.CharField(max_length=180, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Doenca(TimeStampedModel):
    source_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    nome = models.CharField(max_length=220, unique=True)
    tipo = models.CharField(max_length=160, blank=True)
    agente_etiologico = models.CharField(max_length=300, blank=True)
    fase_comum = models.CharField(max_length=180, blank=True)
    sintomas_texto = models.TextField(blank=True)
    sintomas = models.ManyToManyField(Sintoma, related_name="doencas", blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Variavel(TimeStampedModel):
    nome = models.CharField(max_length=220, unique=True)
    descricao = models.TextField(blank=True)
    opcoes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Farmaco(TimeStampedModel):
    source_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    nome_comercial = models.CharField(max_length=220, unique=True)
    principio_ativo = models.CharField(max_length=260, blank=True)
    classe = models.CharField(max_length=220, blank=True)
    indicacoes_principais = models.TextField(blank=True)
    posologia = models.TextField(blank=True)
    via_administracao = models.CharField(max_length=220, blank=True)
    carencia = models.CharField(max_length=220, blank=True)
    contraindicacoes = models.TextField(blank=True)
    reacoes_adversas = models.TextField(blank=True)
    mecanismo_acao = models.TextField(blank=True)
    precaucoes = models.TextField(blank=True)
    doencas_relacionadas = models.ManyToManyField(Doenca, related_name="farmacos", blank=True)

    class Meta:
        ordering = ["nome_comercial"]

    def __str__(self):
        return self.nome_comercial


class Vacina(TimeStampedModel):
    source_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    nome_comercial = models.CharField(max_length=220, unique=True)
    tipo = models.CharField(max_length=160, blank=True)
    doencas_prevenidas = models.TextField(blank=True)
    agentes_alvo = models.TextField(blank=True)
    categoria = models.CharField(max_length=160, blank=True)
    fase_indicada = models.CharField(max_length=220, blank=True)
    idade_recomendada = models.CharField(max_length=180, blank=True)
    dose = models.CharField(max_length=180, blank=True)
    via = models.CharField(max_length=120, blank=True)
    numero_doses = models.CharField(max_length=80, blank=True)
    intervalo_reforco = models.CharField(max_length=180, blank=True)
    inicio_imunidade = models.CharField(max_length=180, blank=True)
    duracao_imunidade = models.CharField(max_length=180, blank=True)
    carencia = models.CharField(max_length=120, blank=True)
    armazenamento = models.CharField(max_length=180, blank=True)
    contraindicacoes = models.TextField(blank=True)
    reacoes_adversas = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["nome_comercial"]

    def __str__(self):
        return self.nome_comercial


class Indicacao(TimeStampedModel):
    medicamento = models.CharField(max_length=220)
    doenca_indicacao = models.CharField(max_length=260)
    tipo = models.CharField(max_length=40)
    prioridade = models.PositiveSmallIntegerField(null=True, blank=True)
    farmaco = models.ForeignKey(Farmaco, null=True, blank=True, on_delete=models.CASCADE, related_name="indicacoes")
    vacina = models.ForeignKey(Vacina, null=True, blank=True, on_delete=models.CASCADE, related_name="indicacoes")
    doenca = models.ForeignKey(Doenca, null=True, blank=True, on_delete=models.SET_NULL, related_name="indicacoes")

    class Meta:
        ordering = ["medicamento", "doenca_indicacao"]
        constraints = [models.UniqueConstraint(fields=["medicamento", "doenca_indicacao", "tipo"], name="indicacao_unica")]


class GeracaoDataset(TimeStampedModel):
    total_registros = models.PositiveIntegerField(default=1520)
    semente = models.PositiveIntegerField(default=42)
    arquivo = models.CharField(max_length=500, blank=True)
    resumo = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class CasoClinico(TimeStampedModel):
    geracao = models.ForeignKey(GeracaoDataset, on_delete=models.CASCADE, related_name="casos")
    numero = models.PositiveIntegerField()
    doenca = models.ForeignKey(Doenca, on_delete=models.PROTECT, related_name="casos_clinicos")
    sintomas = models.JSONField(default=list)
    variaveis = models.JSONField(default=dict)

    class Meta:
        ordering = ["numero"]
        constraints = [models.UniqueConstraint(fields=["geracao", "numero"], name="caso_numero_por_geracao")]
