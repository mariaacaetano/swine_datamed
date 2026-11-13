import "./InferenceModelSwitch.css"
import { useEngineCatalog } from "./useInferenceModel"

function InferenceModelSwitch({ value, onChange, compact = false, disabled = false }) {
  const { models, error } = useEngineCatalog()
  return (
    <fieldset
      className={`inference-switch ${compact ? "inference-switch--compact" : ""}`}
      disabled={disabled}
      title={disabled ? "Este é o motor definido para esta conversa." : "Escolha o motor desta conversa."}
    >
      <legend>Inferência de doenças · leitura e bulário compartilhados</legend>
      {error && <p role="status">Não foi possível consultar os motores: {error}</p>}
      <div>
        {models.map((model) => (
          <button
            type="button"
            role="switch"
            aria-checked={value === model.id}
            disabled={disabled || !model.disponivel}
            className={value === model.id ? "is-active" : ""}
            onClick={() => onChange(model.id)}
            key={model.id}
          >
            {model.modelo || model.nome}{model.padrao ? " · padrão" : ""}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

export default InferenceModelSwitch
