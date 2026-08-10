from django.contrib import admin

from .models import CasoClinico, Doenca, Farmaco, GeracaoDataset, Indicacao, Sintoma, Vacina, Variavel


@admin.register(Farmaco)
class FarmacoAdmin(admin.ModelAdmin):
    list_display = ["nome_comercial", "principio_ativo", "classe", "via_administracao", "carencia"]
    search_fields = ["nome_comercial", "principio_ativo", "classe", "indicacoes_principais"]
    filter_horizontal = ["doencas_relacionadas"]


@admin.register(Doenca)
class DoencaAdmin(admin.ModelAdmin):
    list_display = ["nome", "tipo", "fase_comum"]
    search_fields = ["nome", "tipo", "fase_comum", "sintomas_texto"]
    filter_horizontal = ["sintomas"]


@admin.register(Sintoma)
class SintomaAdmin(admin.ModelAdmin):
    search_fields = ["nome"]


@admin.register(Variavel)
class VariavelAdmin(admin.ModelAdmin):
    search_fields = ["nome", "descricao"]


admin.site.register(Vacina)
admin.site.register(Indicacao)
admin.site.register(GeracaoDataset)
admin.site.register(CasoClinico)
