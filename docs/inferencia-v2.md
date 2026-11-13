# Modelagens e inferência v2

Registro histórico da revisão anterior. Para a implementação atual, veja
[inferência v3](inferencia-v3.md), com Sanchez e Random Forest com quatro estados.

A correção altera a conversão da entrada e o cálculo de alguns motores. Os
resultados anteriores do TCC não descrevem esta versão. É necessário apresentar
os novos resultados como um experimento distinto, com seu protocolo identificado.

## Fatos extraídos

Cada sintoma fica em um único estado: confirmado, explicitamente negado ou
incerto. Uma nova menção atualiza o estado anterior na conversa. Sem menção,
o estado é desconhecido. A negação que integra o próprio sinal, como “sem
apetite”, é preservada; uma negação externa ao sinônimo, como “não está tossindo”,
nega o sinal. A análise é baseada em padrões de texto e similaridade lexical,
não em interpretação geral da língua portuguesa.

Temperatura exige contexto de temperatura/febre ou unidade. Idade e duração
são extraídas separadamente. A última temperatura numérica informada prevalece;
a medida substitui a indicação textual de febre na faixa correspondente.
As faixas de idade são <7, 7–21, 22–70, 71–180 e >180 dias.

## Regras e grafo

O motor heurístico preserva `0,6 cobertura + 0,4 precisão + 0,25 ajuste`, limitado
a [0,1]. O grafo consulta arestas diretas e usa Jaccard com ajuste contextual.
São pontuações heurísticas, não probabilidades. A representação em grafo continua
sem inferência ontológica ou travessia de múltiplas arestas.

O motor encadeado deriva fatos em rodadas até ponto fixo. Evidência incerta
não dispara presença confirmada. Sintoma associado negado impede suporte completo,
mas não exclui uma doença: a base registra associações, sem critérios de sintomas
obrigatórios. A restrição gestacional para macho mantém o bloqueio simbólico,
enquanto divergência de fase deriva suporte restrito. Todas essas regras são
experimentais; suporte completo significa correspondência ao perfil cadastrado.

## Rede Bayesiana em estrela

Para cada doença d e sintoma s, define-se p(s,d)=0,8 se há associação e 0,2 caso
contrário. O prior é uniforme entre doenças com sintomas cadastrados. Para os
mesmos conjuntos P de sinais confirmados e N de sinais negados:

`L(d) = log prior(d) + soma_{s em P} log p(s,d) + soma_{s em N} log(1-p(s,d))`.

A posterior é `exp(L(d)-max L) / soma_k exp(L(k)-max L)` sobre todas as classes,
antes de selecionar até cinco. Sintomas desconhecidos e incertos contribuem
com fator 1, equivalendo à marginalização de variáveis não observadas. A aplicação
se abstém de listar diagnósticos sem sinal confirmado, embora uma rede possa
matematicamente retornar os priors ou inferir apenas de evidências negativas.

É uma rede Naive Bayes: pressupõe independência condicional dos sintomas. Não
modela relações causais adicionais ou dependências entre os sinais. As CPTs
manuais formam um modelo probabilístico consistente, mas são parâmetros
experimentais e não representam prevalências/sensibilidades clínicas estimadas.

## Fuzzy Sugeno de ordem zero

O peso de certeza da observação é 1 para confirmação, 0,5 para incerteza e 0
para sinal negado ou desconhecido. Esse peso é uma escolha experimental separada
da pertinência linguística. Para temperatura numérica, o peso de febre é a rampa
`clip((T-39,5)/0,5,0,1)` e o de febre alta é `clip((T-40)/0,5,0,1)`, sem bônus aditivo.

Para o perfil S_d de uma doença e os pesos w_s:

- Cobertura C = soma dos pesos associados / número de sintomas no perfil.
- Precisão P = soma dos pesos associados / soma de todos os pesos observados.

Desconhecimento não é convertido em negação, mas a cobertura mede quanto do
perfil cadastrado está sustentado e, portanto, diminui com sinais sem suporte.
As funções linguísticas, para x em [0,1], formam uma partição:

- baixo: `max(0,1-2x)`;
- médio: `max(0,1-|2x-1|)`;
- alto: `max(0,2x-1)`.

As nove regras combinam cobertura e precisão. Para centros 0, 0,5 e 1, o
consequente de cada par é o menor dos dois centros. A ativação usa o produto
das duas pertinências, e a saída é a média dos consequentes ponderada pelas
ativações. Exemplo: C=P=0,75 ativa quatro regras com peso 0,25; consequentes
0,5, 0,5, 0,5 e 1 produzem suporte 0,625. A saída é um suporte numérico Sugeno,
não posterior, nem composição max–min de Sanchez. As regras ativas e as entradas
são retornadas para inspeção. Não há candidatas com suporte zero.

## ML e dados ausentes

A seleção supervisionada, o treinamento e os artefatos são preservados. Na
inferência Bernoulli, apenas componentes observados do vetor transformado
participam da verossimilhança; os demais são marginalizados. Para uma categoria
clínica informada e conhecida pelo encoder, todos os indicadores daquela variável
participam, incluindo os zeros complementares. Uma categoria desconhecida pelo
encoder também é marginalizada. Sinais explicitamente negados participam como
zero observado. Não há multiplicação posterior por penalidades manuais.

Random Forest e outros classificadores existentes recebem a representação binária
do treinamento, com zero também para sintomas desconhecidos/incertos. A saída
explicita essa limitação. Distinguir esses estados em árvores exigiria um novo
conjunto de treinamento com estados de observação e uma nova avaliação.

O fallback analítico usa contagens das combinações sintéticas, evidência comum
e marginalização. Normaliza todas as classes antes do limite de retorno. Ele
é identificado como fallback, sem alegar execução de um artefato treinado.

## Avaliação e significado da saída

Os três comandos de avaliação chamam a implementação real dos motores.
`evaluate_classification` e `evaluate_all_models` avaliam os seis motores;
`evaluate_knowledge` avalia Bayes e Fuzzy nos dois conjuntos. A entrada do
protocolo permanece somente o texto dos sintomas positivos do CSV: os zeros
do CSV não são fornecidos como negações. Variáveis clínicas também não são
fornecidas. Os tempos se referem às entradas distintas, pois há cache.

Precisão@5 usa o número efetivo de hipóteses, recall@5 equivale à proporção
de rótulos recuperados e F1 usa os contadores micro. Os resultados incluem
`inferencia_corrigida_v2` e são gravados em arquivos separados dos históricos.

A interface não compara scores como se tivessem a mesma escala probabilística.
Confiança clínica e adequação clínica permanecem não estimadas/não avaliadas.
Fármacos são associações recuperadas após a classificação, sem avaliação de
adequação de tratamento pelo motor. Dados e parâmetros permanecem sintéticos
ou experimentais; esta correção não fornece validação clínica externa.

## Execução registrada em 12/10/2026

Arquivo: `config/machine/artifacts/classification_metrics_corrected.json`.

São 3.100 registros sintéticos e 300 entradas textuais distintas, com somente
sintomas positivos. A cobertura de conversão foi 0,991659 em todos os motores.

| Motor | Acurácia@1 | Recuperação@5 |
|---|---:|---:|
| Regras heurísticas | 0.5161 | 0.7839 |
| Regras encadeadas | 0.0645 | 0.3290 |
| Grafo / Jaccard | 0.7387 | 0.9258 |
| ML / Bernoulli Naive Bayes | 0.8226 | 0.9710 |
| Naive Bayes parametrizado | 0.8355 | 0.9742 |
| Fuzzy / Sugeno | 0.6871 | 0.9161 |

Os empates entre categorias ordinais das regras encadeadas são resolvidos
alfabeticamente; essa limitação afeta seu ranking. Os números medem recuperação
dos rótulos sintéticos e não demonstram generalização para casos clínicos reais.
