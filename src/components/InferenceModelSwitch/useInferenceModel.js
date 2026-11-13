import { useEffect, useState } from "react"
import { requestJson } from "../../services/api"

const storageKey = "swine-inference-model-v4"
const changedEvent = "swine-inference-model-changed"
const defaultModel = "machine_learning"

function readModel() {
  try { return localStorage.getItem(storageKey) || defaultModel } catch { return defaultModel }
}

export function useEngineCatalog() {
  const [catalog, setCatalog] = useState({ models: [], error: "" })
  useEffect(() => {
    const controller = new AbortController()
    requestJson("/pipeline/", { signal: controller.signal }).then((data) => {
      setCatalog({ models: data.motores, error: "" })
    }).catch((error) => {
      if (!controller.signal.aborted) setCatalog({ models: [], error: error.message })
    })
    return () => controller.abort()
  }, [])
  return catalog
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
    try { localStorage.setItem(storageKey, nextModel) } catch { return setModel(nextModel) }
    setModel(nextModel)
    window.dispatchEvent(new Event(changedEvent))
  }
  return [model, selectModel]
}
