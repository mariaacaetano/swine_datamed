const errorMessages = {
  "not-allowed": "O acesso ao microfone foi bloqueado. No Chrome, abra as permissões deste site e permita o Microfone; habilitar apenas o Som não libera a captura de voz.",
  "service-not-allowed": "O Chrome bloqueou o serviço de reconhecimento de voz. Verifique as permissões do site e as restrições do navegador.",
  "audio-capture": "Não foi possível captar áudio. Confira se o microfone está conectado e selecionado no Chrome e se o sistema permite usá-lo.",
  network: "O Chrome não conseguiu conectar ao serviço de reconhecimento de voz. Confira a conexão e tente novamente; permitir o microfone não resolve uma falha desse serviço.",
  "language-not-supported": "O serviço de voz deste navegador não oferece reconhecimento em português. Você pode digitar os sintomas.",
}

export function voiceErrorMessage(error) {
  return errorMessages[error] || "Não foi possível iniciar o reconhecimento de voz. Clique no microfone para tentar novamente ou digite os sintomas."
}

export function createVoiceRecognition(Recognition, { onState, onResult }, timers = globalThis) {
  const recognition = new Recognition()
  recognition.lang = "pt-BR"
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 3

  let enabled = false
  let active = false
  let restarting = false
  let disposed = false
  let restartTimer
  let status = "idle"

  const clearRestart = () => timers.clearTimeout(restartTimer)
  const updateState = (nextStatus, error = "") => {
    status = nextStatus
    onState({ status, enabled, error })
  }

  const start = () => {
    if (disposed) return
    enabled = true
    clearRestart()
    if (active) return
    active = true
    updateState("starting")
    try {
      recognition.start()
    } catch (error) {
      active = false
      enabled = false
      updateState("error", voiceErrorMessage(error.name === "NotAllowedError" ? "not-allowed" : error.name))
    }
  }

  recognition.onstart = () => {
    if (!disposed && enabled && !restarting) updateState("listening")
  }
  recognition.onresult = (event) => {
    if (!disposed && enabled && !restarting) onResult(event)
  }
  recognition.onerror = (event) => {
    if (disposed || !enabled) return
    if (event.error === "no-speech" || event.error === "aborted") return
    enabled = false
    clearRestart()
    updateState("error", voiceErrorMessage(event.error))
  }
  recognition.onend = () => {
    active = false
    restarting = false
    if (disposed) return
    clearRestart()
    if (enabled) {
      updateState("starting")
      restartTimer = timers.setTimeout(start, 450)
    } else if (status !== "error") {
      updateState("idle")
    }
  }

  return {
    start,
    restart() {
      if (disposed || !enabled || restarting) return
      clearRestart()
      if (active) {
        restarting = true
        updateState("starting")
        recognition.abort()
      } else {
        start()
      }
    },
    stop() {
      enabled = false
      clearRestart()
      updateState("idle")
      if (active) recognition.abort()
    },
    dispose() {
      disposed = true
      enabled = false
      clearRestart()
      recognition.onstart = null
      recognition.onresult = null
      recognition.onerror = null
      recognition.onend = null
      if (active) recognition.abort()
    },
  }
}
