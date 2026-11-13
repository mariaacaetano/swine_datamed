import { useState } from "react"
import "./ClinicalContext.css"

const fields = [
  { key: "temperatura_corporal_c", label: "Corporal (°C)", min: 30, max: 45, step: 0.1 },
  { key: "temperatura_ambiente_c", label: "Ambiente (°C)", min: -30, max: 60, step: 0.1 },
  { key: "idade_dias", label: "Idade (dias)", min: 0, max: 10000, step: 1 },
  { key: "duracao_horas", label: "Duração dos sinais (horas)", min: 0, max: 87600, step: 1 },
  { key: "peso_kg", label: "Peso (kg)", min: 0, max: 2000, step: 0.1 },
  { key: "animais_afetados", label: "Animais afetados", min: 0, max: 1000000, step: 1 },
]

export default function ClinicalContext({ onSubmit, disabled, result }) {
  const [draft, setDraft] = useState({})
  const submit = async (event) => {
    event.preventDefault()
    const data = Object.fromEntries(Object.entries(draft).filter(([, value]) => value !== "")
      .map(([key, value]) => [key, fields.some((field) => field.key === key) ? Number(value) : value]))
    if (!Object.keys(data).length) return
    if (await onSubmit("", data)) setDraft({})
  }
  return (
    <details className="clinical-context">
      <summary>Dados do animal e do ambiente</summary>
      {result?.variaveis_reconhecidas && <p>Os dados já informados permanecem no contexto. Preencha apenas o que deseja acrescentar ou corrigir.</p>}
      <form onSubmit={submit}>
        <fieldset disabled={disabled}>
          {fields.map((field) => <label key={field.key}>{field.label}
            <input type="number" min={field.min} max={field.max} step={field.step}
              value={draft[field.key] ?? ""} placeholder="Não informado"
              onChange={(event) => setDraft((current) => ({ ...current, [field.key]: event.target.value }))} />
          </label>)}
          <label>Fase<select value={draft.fase_reprodutiva || ""} onChange={(event) => setDraft((current) => ({ ...current, fase_reprodutiva: event.target.value }))}>
            <option value="">Não informada</option>
            {["Leitão maternidade", "Creche", "Crescimento", "Terminação", "Matriz", "Reprodutor"].map((value) => <option key={value}>{value}</option>)}
          </select></label>
          <label>Tipo de suíno<select value={draft.tipo_suino || ""} onChange={(event) => setDraft((current) => ({ ...current, tipo_suino: event.target.value }))}>
            <option value="">Não informado</option>
            {["Leitão maternidade", "Leitoa", "Matriz", "Reprodutor", "Cachaço"].map((value) => <option key={value}>{value}</option>)}
          </select></label>
          <label>Sexo<select value={draft.genero || ""} onChange={(event) => setDraft((current) => ({ ...current, genero: event.target.value }))}>
            <option value="">Não informado</option>
            {["Macho inteiro", "Macho castrado", "Fêmea"].map((value) => <option key={value}>{value}</option>)}
          </select></label>
          <label>Estado reprodutivo<select value={draft.estado_reprodutivo || ""} onChange={(event) => setDraft((current) => ({ ...current, estado_reprodutivo: event.target.value }))}>
            <option value="">Não informado</option>
            {["Gestante", "Lactante", "Vazia", "Não aplicável"].map((value) => <option key={value}>{value}</option>)}
          </select></label>
        </fieldset>
        <button type="submit" disabled={disabled || !Object.values(draft).some((value) => value !== "")}>Atualizar triagem</button>
      </form>
    </details>
  )
}
