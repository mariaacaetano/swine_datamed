import "./InferenceModelSwitch.css"

const inferenceModels = [
  { value: "regras", label: "Regras" },
  { value: "semantica", label: "Semântica" },
  { value: "machine_learning", label: "ML" },
]

function InferenceModelSwitch({ value, onChange, compact = false, disabled = false }) {
  return (
    <fieldset
      className={`inference-switch ${compact ? "inference-switch--compact" : ""}`}
      disabled={disabled}
      title={disabled ? "Este é o motor definido para esta conversa." : "Escolha o motor desta conversa."}
    >
      <legend>Motor de inferência</legend>
      <div>
        {inferenceModels.map((model) => (
          <button
            type="button"
            role="switch"
            aria-checked={value === model.value}
            disabled={disabled}
            className={value === model.value ? "is-active" : ""}
            onClick={() => onChange(model.value)}
            key={model.value}
          >
            {model.label}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

export default InferenceModelSwitch
