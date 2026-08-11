import { useEffect, useState } from "react"

const storageKey = "swine-inference-model"
const changedEvent = "swine-inference-model-changed"
const validModels = new Set(["regras", "semantica", "machine_learning"])

function readModel() {
  const saved = localStorage.getItem(storageKey)
  return validModels.has(saved) ? saved : "regras"
}

export function useInferenceModel() {
  const [model, setModel] = useState(readModel)

  useEffect(() => {
    const update = () => setModel(readModel())
    window.addEventListener(changedEvent, update)
    window.addEventListener("storage", update)
    return () => {
      window.removeEventListener(changedEvent, update)
      window.removeEventListener("storage", update)
    }
  }, [])

  const selectModel = (nextModel) => {
    localStorage.setItem(storageKey, nextModel)
    setModel(nextModel)
    window.dispatchEvent(new Event(changedEvent))
  }

  return [model, selectModel]
}
