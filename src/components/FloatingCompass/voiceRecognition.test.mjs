import assert from "node:assert/strict"
import test from "node:test"
import { createVoiceRecognition } from "./voiceRecognition.js"

function setup() {
  let recognition
  class Recognition {
    starts = 0
    aborts = 0
    constructor() { recognition = this }
    start() {
      this.starts += 1
      if (this.startError) throw this.startError
    }
    abort() { this.aborts += 1 }
  }
  const scheduled = new Map()
  let timerId = 0
  const timers = {
    setTimeout(callback) { scheduled.set(++timerId, callback); return timerId },
    clearTimeout(id) { scheduled.delete(id) },
  }
  const states = []
  const results = []
  const voice = createVoiceRecognition(Recognition, {
    onState: (state) => states.push(state),
    onResult: (event) => results.push(event),
  }, timers)
  return {
    voice, recognition, states, results, scheduled,
    runTimer() {
      const [id, callback] = scheduled.entries().next().value
      scheduled.delete(id)
      callback()
    },
  }
}

test("confirma escuta somente após o Chrome iniciar e evita sessões simultâneas", () => {
  const { voice, recognition, states } = setup()
  voice.start()
  voice.start()
  assert.equal(recognition.starts, 1)
  assert.equal(states.at(-1).status, "starting")
  recognition.onstart()
  assert.equal(states.at(-1).status, "listening")
  assert.equal(recognition.lang, "pt-BR")
  assert.equal(recognition.interimResults, true)
})

test("retoma a escuta quando o Chrome encerra por silêncio", () => {
  const { voice, recognition, scheduled, runTimer } = setup()
  voice.start()
  recognition.onerror({ error: "no-speech" })
  recognition.onend()
  assert.equal(scheduled.size, 1)
  runTimer()
  assert.equal(recognition.starts, 2)
})

test("renova a escuta ao fechar o painel e ignora resultados da sessão anterior", () => {
  const { voice, recognition, states, results, scheduled, runTimer } = setup()
  voice.start()
  recognition.onstart()
  voice.restart()
  voice.restart()
  assert.equal(recognition.aborts, 1)
  assert.equal(states.at(-1).enabled, true)
  assert.equal(states.at(-1).status, "starting")
  recognition.onstart()
  recognition.onresult({ resultIndex: 0, results: [] })
  assert.equal(states.at(-1).status, "starting")
  assert.equal(results.length, 0)
  recognition.onerror({ error: "aborted" })
  recognition.onend()
  assert.equal(scheduled.size, 1)
  runTimer()
  recognition.onstart()
  const event = { resultIndex: 0, results: [] }
  recognition.onresult(event)
  assert.equal(recognition.starts, 2)
  assert.equal(states.at(-1).status, "listening")
  assert.equal(results[0], event)
})

test("fechar o painel não reativa uma escuta desligada manualmente", () => {
  const { voice, recognition, scheduled } = setup()
  voice.start()
  voice.stop()
  voice.restart()
  recognition.onend()
  assert.equal(recognition.starts, 1)
  assert.equal(recognition.aborts, 1)
  assert.equal(scheduled.size, 0)
})

test("desligar durante a renovação cancela a retomada", () => {
  const { voice, recognition, states, scheduled } = setup()
  voice.start()
  voice.restart()
  voice.stop()
  recognition.onend()
  assert.equal(states.at(-1).enabled, false)
  assert.equal(scheduled.size, 0)
})

for (const error of ["not-allowed", "service-not-allowed", "audio-capture", "network"]) {
  test(`explica ${error} e interrompe as tentativas automáticas`, () => {
    const { voice, recognition, states, scheduled } = setup()
    voice.start()
    recognition.onerror({ error })
    recognition.onend()
    assert.equal(states.at(-1).status, "error")
    assert.equal(states.at(-1).enabled, false)
    assert.ok(states.at(-1).error.length > 0)
    assert.equal(scheduled.size, 0)
    voice.start()
    assert.equal(recognition.starts, 2)
    assert.equal(states.at(-1).error, "")
  })
}

test("permite desligar enquanto aguarda permissão e ignora resultados tardios", () => {
  const { voice, recognition, states, results, scheduled } = setup()
  voice.start()
  voice.stop()
  recognition.onstart()
  recognition.onresult({ results: [] })
  recognition.onerror({ error: "aborted" })
  recognition.onend()
  assert.equal(recognition.aborts, 1)
  assert.equal(states.at(-1).status, "idle")
  assert.equal(results.length, 0)
  assert.equal(scheduled.size, 0)
})

test("limpa callbacks e retomadas ao desmontar, inclusive no StrictMode", () => {
  const { voice, recognition, scheduled } = setup()
  voice.start()
  const oldEnd = recognition.onend
  recognition.onend()
  voice.dispose()
  oldEnd()
  assert.equal(recognition.onend, null)
  assert.equal(recognition.onresult, null)
  assert.equal(scheduled.size, 0)
  voice.start()
  assert.equal(recognition.starts, 1)
})

test("falha síncrona ao iniciar apresenta a orientação de permissão", () => {
  const { voice, recognition, states } = setup()
  recognition.startError = { name: "NotAllowedError" }
  voice.start()
  assert.equal(states.at(-1).enabled, false)
  assert.match(states.at(-1).error, /Microfone/)
})

test("encaminha resultados parciais para detectar a frase sem esperar silêncio", () => {
  const { voice, recognition, results } = setup()
  voice.start()
  const event = { resultIndex: 0, results: [{ 0: { transcript: "ei, data med" }, isFinal: false }] }
  recognition.onresult(event)
  assert.equal(results[0], event)
})
