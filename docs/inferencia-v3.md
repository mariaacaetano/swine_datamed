# Modelagens e inferência v3

Esta versão separa os processos matemáticos, preserva os estados relatados e
identifica lacunas da base. Resultados históricos e artefatos anteriores são
mantidos em arquivos próprios. A base disponível contém associações e não casos
clínicos: os parâmetros e as observações simuladas não são estimativas clínicas.

## Relato → fatos → representação → inferência

O extrator é compartilhado pelos oito motores. Presença, negação e incerteza são
estados diferentes; omissão significa desconhecimento. A última menção do mesmo
sinal ou atributo atualiza o estado. Sinônimos com negação intrínseca, como
“sem apetite”, ainda afirmam o sinal correspondente, salvo negação externa.

Exemplos verificados:

- “Sem febre, tosse ou diarreia”: os três sinais são negados.
- “Fêmea não gestante com tosse”: tosse confirmada; gestação negada.
- “Temperatura não é 40 °C”: nenhuma temperatura confirmada ou febre derivada.
- “Creche; correção: terminação”: a fase final é terminação.
- “Febre; sem febre alta”: febre confirmada, febre alta negada.
- “Talvez tosse”: observação incerta, sem confirmação de presença.

Nomes específicos prevalecem sobre correspondências contidas na mesma expressão;
não se propagam estados entre sinais diferentes sem uma ontologia que estabeleça
essas relações. Nomes compostos e hífens são preservados ao converter CSV para
texto; o extrator também aceita hífen relatado como espaço. Idade não é confundida
com duração dos sinais. A extração continua baseada em padrões e similaridade
lexical; os testes não demonstram compreensão irrestrita de linguagem natural.

## Fonte e lacunas

A auditoria encontrou 112 doenças e 80 registros no vocabulário de sintomas.
Um registro, “Não informado no documento”, é um marcador de lacuna, único vínculo
sintomático de 32 doenças. Existem 79 sinais e 80 doenças com perfis documentados.
O marcador fica preservado na origem e não fornece evidência, atributo de treino
ou perfil diagnóstico. Os nomes das doenças sem sinais e os hashes das fontes
estão em `config/bulario/domain_audit_v3.json`.

Não foram inventados sinais para completar esses perfis. Associação também não
significa sintoma obrigatório, intensidade de relação ou frequência clínica.

## Motores

| Chave | Processo implementado | Significado do score |
|---|---|---|
| `regras` | Seleção por evidência e soma heurística de cobertura, precisão e contexto | Pontuação heurística |
| `regras_encadeadas` | Regras E1–E8 em rodadas até ponto fixo, com trilha | Categoria ordinal |
| `semantica` | Consulta de arestas diretas Sintoma → Doença e Jaccard ajustado | Similaridade |
| `machine_learning` / `machine_learning_k100` | Bernoulli NB histórico com verossimilhança parcial | Posterior no modelo sintético |
| `machine_learning_k10` | Random Forest retreinado com quatro estados por sintoma | Probabilidade no classificador sintético |
| `rede_bayesiana` | Naive Bayes em estrela com CPTs manuais e evidência comum | Posterior no modelo manual |
| `fuzzy` | Sugeno de ordem zero com nove regras e consequentes constantes | Suporte Sugeno |
| `fuzzy_sanchez` | Composição paciente–sintoma ∘ sintoma–doença, max–min | Grau da composição |

O grafo não executa inferência ontológica ou travessia multissalto. Regras e
Jaccard mantêm ajustes experimentais. O encadeamento não elimina uma doença
simplesmente porque um sinal associado foi negado. Confiança e adequação clínicas
continuam não estimadas; a consulta posterior de fármacos recupera associações.

### Sanchez

`grau(d) = max_s min(grau_observado(s), grau_relacao(s,d))`.

A operação segue a composição de relações de
[Sanchez (1976)](https://www.sciencedirect.com/science/article/pii/S0019995876904460).
O código expõe os mínimos por sinal e conta todos os empates no maior grau antes
do corte. O operador numérico aceita relações graduadas em [0,1]; o motor usa
R=1 para vínculos cadastrados e R=0 para os demais, pois não há graus documentados.

Os pesos da observação são os mesmos do Sugeno: confirmação=1, incerteza=0,5;
febre medida utiliza rampas contínuas experimentais. Negações e desconhecimentos
não fornecem suporte positivo. Essa versão não acrescenta média ou penalidades
à composição e não utiliza uma relação complementar para diagnóstico diferencial.
Um único sinal confirmado pode produzir grau 1 em várias doenças; o empate
alfabético organiza a saída e não acrescenta poder diagnóstico.

### Random Forest e treinamento

`presente`, `ausente`, `incerto` e `desconhecido` têm indicadores one-hot distintos,
com o mesmo esquema no treino e no texto de entrada. O novo treino inclui contexto
clínico “Não informado”. O artefato está em `config/machine/artifacts_states`,
com seleção explícita de Random Forest, sem alegar vitória em uma comparação.

A simulação deriva das partições k=10 e conserva grupos e rótulos de origem. As
taxas iniciais, experimentais, são presença=0,65 e incerteza=0,15 para sintomas
positivos do perfil; ausência relatada=0,05 para zeros; omissão do contexto=0,5.
Cada registro conserva um sinal confirmado, alterando as frequências finais.
Zeros combinatórios não demonstram ausência clínica. As taxas podem ser alteradas
pelos argumentos de `generate_ml_observations` e ficam registradas nos metadados.

O marcador documental é excluído e 320 linhas sem sinais reais foram retiradas
do treino. O conjunto contém 14.320 registros de treino, 3.100 de validação e
3.100 de teste. As colunas binárias de origem são auditáveis, mas não entram nos
atributos nem na inferência do avaliador com estados. A geração e o treino recusam
grupos compartilhados entre partições. Hashes, semente e contagens são registrados.

O Bernoulli NB histórico continua usando seu artefato e marginaliza atributos
desconhecidos/incertos. Ambos os classificadores restringem as hipóteses às
classes cadastradas com perfil documentado, normalizando a massa sobre esse
universo antes do corte. Sintomas explicitamente negados participam da
verossimilhança Bernoulli como zeros observados, sem penalidade posterior.

### Bayes e cenário real

O modelo manual usa o mesmo conjunto de sinais observados/negados para todas
as doenças, prior uniforme e probabilidades complementares para ausência.
Os valores 0,8 e 0,2 já eram identificados como experimentais no TCC histórico.
A metodologia do TCC explicita o algoritmo e a origem dos parâmetros.

Somente vínculos não identificam `P(sinal|doença)` nem prevalência. Enumerar
combinações permite estimar frequências do gerador, sem transformá-las em
frequências clínicas. A revisão preserva essa distinção e permite variar os
dois parâmetros com validação `0 < p_nao_associado < p_associado < 1`.

O ensaio de sensibilidade compara nove cenários manuais em 300 entradas distintas,
com semente 42: associado ∈ {0,6; 0,8; 0,95}, não associado ∈ {0,05; 0,2; 0,4}.
Mede concordância da primeira hipótese e Jaccard das cinco hipóteses em relação
a 0,8/0,2. Não ajusta parâmetros pelo alvo nem escolhe uma configuração clínica.
Com evidência só positiva, a ordenação pela quantidade de associações é preservada
para qualquer par com associado > não associado; estabilidade de ranking não
valida probabilidades absolutas. Priors e CPTs clínicos exigiriam outra fonte.

## Reprodução

Na raiz do aplicativo, com a base importada e as partições k=10 existentes:

```bash
./venv/bin/python config/manage.py audit_domain_base
./venv/bin/python config/manage.py generate_ml_observations
./venv/bin/python config/manage.py train_ml --data-dir generated_data/machine_learning_states --artifact-dir config/machine/artifacts_states --model random_forest
./venv/bin/python config/manage.py evaluate_classification
./venv/bin/python config/manage.py evaluate_classification --data generated_data/machine_learning_states/teste.csv --sample-size 300 --output config/machine/artifacts_states/classification_metrics_v3.json
./venv/bin/python config/manage.py evaluate_bayesian_sensitivity
./venv/bin/python config/manage.py test bulario regras semantica machine users suinos
```

Os avaliadores chamam os motores reais, com cache por entrada. Todos recebem os
mesmos sintomas relatados e omissão do contexto; rótulos são usados apenas na
contagem posterior. Listas efetivamente retornadas determinam os contadores micro.
O ensaio com estados é uma amostra de 300 dos 3.100 registros, identificada por
semente e tamanho no arquivo. As métricas de treino do próprio RF usam todo o
teste com contexto clínico simulado e pertencem a um protocolo distinto.

## Execução registrada em 12/10/2026

O ensaio de sintomas positivos contém 3.100 registros e 300 textos distintos.
O ensaio de estados contém uma amostra determinística de 300 dos 3.100 registros
de teste. A cobertura dos sinais confirmados esperados foi 1,0 nos dois ensaios;
isso verifica os textos do gerador, sem demonstrar compreensão geral da linguagem.

| Motor | Acurácia@1, positivos | Recuperação@5, positivos | Acurácia@1, estados | Recuperação@5, estados |
|---|---:|---:|---:|---:|
| Regras heurísticas | 0,5613 | 0,8290 | 0,4467 | 0,7967 |
| Regras encadeadas | 0,0742 | 0,3677 | 0,1333 | 0,5100 |
| Grafo / Jaccard | 0,7355 | 0,9323 | 0,4833 | 0,8267 |
| Bernoulli NB supervisionado | 0,8516 | 0,9742 | 0,7400 | 0,9567 |
| Random Forest com estados | 0,8355 | 0,9516 | 0,7067 | 0,9367 |
| Naive Bayes manual | 0,8710 | 0,9774 | 0,6667 | 0,8933 |
| Sugeno | 0,7097 | 0,9194 | 0,5167 | 0,8500 |
| Sanchez | 0,0903 | 0,4097 | 0,1533 | 0,5333 |

Arquivos: `config/machine/artifacts/classification_metrics_v3.json` e
`config/machine/artifacts_states/classification_metrics_v3.json`. As colunas
pertencem a protocolos e tamanhos diferentes e não isolam o efeito dos estados.
Os empates ordinais e a relação binária de Sanchez limitam seus rankings.

No teste do treinamento do RF, com os 3.100 registros e contexto simulado do CSV,
a acurácia foi 0,7942, o F1-macro foi 0,3294 e a recuperação@5 foi 0,9490.
Esses números estão em `config/machine/artifacts_states/metrics.json` e não
descrevem o protocolo textual sem contexto da tabela.

Na sensibilidade bayesiana, a concordância da primeira hipótese variou de
0,9567 a 1,0 e o Jaccard médio das cinco hipóteses de 0,8892 a 1,0. O relatório
é `config/machine/artifacts_states/bayesian_sensitivity.json`. São resultados
sintéticos de estabilidade em relação à referência manual, sem calibração clínica.

Verificação: 82 testes de backend aprovados, build do frontend concluído, lint
dos componentes alterados aprovado e PDF do TCC recompilado. A metodologia, os resultados e a conclusão do TCC descrevem os oito motores
e os protocolos avaliados, sem uma seção separada de atualizações.
