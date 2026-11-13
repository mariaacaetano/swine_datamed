const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001/api"

export async function requestCollection(path, options = {}) {
  const items = []
  let page = 1
  while (true) {
    const separator = path.includes("?") ? "&" : "?"
    const data = await requestJson(`${path}${separator}page=${page}`, options)
    if (Array.isArray(data)) return [...items, ...data]
    items.push(...data.results)
    if (!data.next) return items
    page += 1
  }
}

export async function requestJson(path, options = {}) {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  options.signal?.addEventListener("abort", abort, { once: true })
  const timeout = window.setTimeout(abort, 30000)
  try {
    const isFormData = options.body instanceof FormData
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options, signal: controller.signal,
      headers: { ...(!isFormData ? { "Content-Type": "application/json" } : {}), ...options.headers },
    })
    const data = response.status === 204 ? null : await response.json().catch(() => ({}))
    if (!response.ok) {
      const error = new Error(data?.detail || data?.non_field_errors?.[0] ||
        Object.values(data || {}).flat().join(" ") || "Não foi possível completar a solicitação.")
      error.status = response.status
      throw error
    }
    return data
  } catch (error) {
    if (controller.signal.aborted && !options.signal?.aborted) throw new Error("O servidor demorou para responder. Tente novamente.", { cause: error })
    throw error
  } finally {
    window.clearTimeout(timeout)
    options.signal?.removeEventListener("abort", abort)
  }
}
