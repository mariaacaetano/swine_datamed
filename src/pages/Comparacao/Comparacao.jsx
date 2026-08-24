import { useState } from "react"
import { Activity, CheckCircle2, Clock3, GitCompareArrows, Play, Stethoscope } from "lucide-react"
import { compararInferencias } from "../../services/inferencia"
import "./Comparacao.css"

const names = {
  regras: "Regras",
  semantica: "Semântica",
  machine_learning_k10: "Random Forest (k=10)",
  machine_learning_k100: "Random Forest (k≈100)",
  rede_bayesiana: "Rede Bayesiana",
  fuzzy: "Lógica Fuzzy",
}

function formatSeconds(value) {
  return Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 5,
  })
}

function Comparacao() {
  const [text, setText] = useState("tosse, febre e dificuldade respiratória")
  const [comparison, setComparison] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const runComparison = async (event) => {
    event.preventDefault()
    if (!text.trim() || loading) return
    setLoading(true)
    setError("")
    try {
      setComparison(await compararInferencias(text.trim()))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="comparison-page">
      <header className="comparison-hero">
        <span><GitCompareArrows size={18} /> Experimentos</span>
        <h1>Painel comparativo</h1>
        <p>Execute o mesmo caso nos seis motores e compare métricas operacionais e hipóteses.</p>
      </header>

      <form className="comparison-form" onSubmit={runComparison}>
        <label htmlFor="comparison-case">Caso clínico para comparação</label>
        <textarea id="comparison-case" value={text} onChange={(event) => setText(event.target.value)} rows={3} />
        <button type="submit" disabled={loading || !text.trim()}>
          <Play size={18} /> {loading ? "Executando..." : "Comparar motores"}
        </button>
      </form>

      {error && <p className="comparison-error">{error}</p>}

      {comparison && (
        <>
          <section className="comparison-summary">
            <article>
              <CheckCircle2 size={22} />
              <div><span>Concordância Top-1</span><strong>{comparison.concordancia_top_1 ? "Sim" : "Não"}</strong></div>
            </article>
            <article>
              <Stethoscope size={22} />
              <div><span>Motores executados</span><strong>{comparison.resultados.length}</strong></div>
            </article>
          </section>

          <section className="comparison-grid">
            {comparison.resultados.map((result) => (
              <article className="comparison-card" key={result.mecanismo}>
                <header>
                  <div><Activity size={20} /><h2>{names[result.mecanismo] || result.mecanismo}</h2></div>
                  <span className="comparison-model-tag">{result.mecanismo}</span>
                  <strong><Clock3 size={16} /> {formatSeconds(result.metricas_sistema.tempo_resposta_s)} s</strong>
                </header>
                <dl>
                  <div><dt>Sintomas</dt><dd>{result.metricas_sistema.sintomas_reconhecidos}</dd></div>
                  <div><dt>Hipóteses</dt><dd>{result.metricas_sistema.hipoteses_retornadas}</dd></div>
                  <div><dt>Fármacos</dt><dd>{result.metricas_sistema.farmacos_retornados}</dd></div>
                  <div><dt>Variáveis</dt><dd>{result.metricas_sistema.variaveis_reconhecidas}</dd></div>
                </dl>
                {result.avaliacao && <div className="comparison-evaluation">
                  <span>Classificação: <strong>{result.avaliacao.classificacao_sintomas}</strong></span>
                  <span>Confiança: <strong>{result.avaliacao.confianca_diagnostica}</strong></span>
                  <span>Tratamento: <strong>{result.avaliacao.recomendacao_tratamento}</strong></span>
                  <span>Fase: <strong>{result.avaliacao.criterios_modelo.fase_mais_adequada}</strong></span>
                  <span>Finalidade: <strong>{result.avaliacao.criterios_modelo.finalidade}</strong></span>
                  <span>Incerteza: <strong>{result.avaliacao.criterios_modelo.tratamento_incerteza}</strong></span>
                  <span>Interpretabilidade: <strong>{result.avaliacao.criterios_modelo.interpretabilidade}</strong></span>
                  <span>Adequação clínica: <strong>{result.avaliacao.criterios_modelo.adequacao_clinica}</strong></span>
                </div>}
                <h3>Ranking</h3>
                {result.hipoteses.length ? (
                  <ol>{result.hipoteses.map((item) => <li key={item.id}><span>{item.nome}</span><strong>{(item.score * 100).toFixed(1)}%</strong></li>)}</ol>
                ) : <p>Nenhuma hipótese encontrada.</p>}
              </article>
            ))}
          </section>
          <p className="comparison-note">{comparison.observacao_metricas_preditivas}</p>
        </>
      )}
    </main>
  )
}

export default Comparacao
