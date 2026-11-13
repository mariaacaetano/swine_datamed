import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { mkdtemp, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

const baseUrl = process.env.SWINE_URL || "http://localhost:5174"
const port = 9400 + Math.floor(Math.random() * 400)
const profile = await mkdtemp(join(tmpdir(), "swine-browser-"))
const chrome = spawn(process.env.CHROME_BINARY || "google-chrome", ["--headless=new", "--no-sandbox",
  "--disable-gpu", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" })
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
const errors = []
let socket
try {
  let target
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      target = await fetch(`http://localhost:${port}/json/new?about:blank`, { method: "PUT" }).then((response) => response.json())
      break
    } catch {
      await delay(100)
    }
  }
  assert.ok(target, "Chrome não iniciou")
  socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.addEventListener("open", resolve); socket.addEventListener("error", reject) })
  let sequence = 0
  const pending = new Map()
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data)
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text)
    if (!message.id) return
    const callback = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) callback.reject(new Error(message.error.message))
    else callback.resolve(message.result)
  })
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    sequence += 1
    pending.set(sequence, { resolve, reject })
    socket.send(JSON.stringify({ id: sequence, method, params }))
  })
  const evaluate = async (expression) => {
    const result = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result.value
  }
  const waitFor = async (expression) => {
    for (let attempt = 0; attempt < 200; attempt += 1) {
      if (await evaluate(expression)) return
      await delay(100)
    }
    throw new Error(`Condição não satisfeita: ${expression}`)
  }
  const send = async (text, panel = false) => {
    const selector = panel ? ".floating-compass__panel textarea" : ".chat-input textarea"
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`)
    await call("Input.insertText", { text })
    const button = panel ? '.floating-compass__panel button[aria-label="Enviar dados da triagem"]' : '.chat-input button[type="submit"]'
    await evaluate(`document.querySelector(${JSON.stringify(button)}).click()`)
    await waitFor(`!document.querySelector(${JSON.stringify(selector)}).value && !document.querySelector('.chat-message--pending, .floating-compass__message--pending')`)
  }
  await call("Runtime.enable")
  await call("Page.enable")
  await call("Network.enable")
  await call("Network.setBlockedURLs", { urls: ["*vlibras.gov.br/*"] })
  await call("Page.navigate", { url: `${baseUrl}/chat` })
  await waitFor("Boolean(document.querySelector('.chat-input textarea'))")
  await send("Leitoa de 2 meses de idade com tosse há 2 dias. Temperatura ambiente 32 graus. Temperatura corporal 40,2 °C.")
  assert.ok(await evaluate("document.querySelector('.chat-messages').innerText.includes('idade em dias: 60')"))
  assert.ok(await evaluate("document.querySelector('.chat-messages').innerText.includes('ambiente (°C): 32')"))
  await send("Correção: temperatura corporal 38,5 °C; sem tosse. Agora apresenta vômito.")
  let last = await evaluate("document.querySelector('.chat-message:last-child').innerText")
  assert.match(last, /corporal \(°C\): 38.5/)
  assert.match(last, /Sinais negados: Tosse/)
  assert.match(last, /Vômito/)
  await evaluate("document.querySelector('.clinical-context summary').click(); [...document.querySelectorAll('.clinical-context label')].find(label => label.textContent.includes('Ambiente')).querySelector('input').focus()")
  await call("Input.insertText", { text: "25" })
  await evaluate("document.querySelector('.clinical-context button[type=submit]').click()")
  await waitFor("!document.querySelector('.chat-message--pending') && document.querySelector('.chat-message:last-child').innerText.includes('ambiente (°C): 25')")
  await send("Quais fármacos estão associados às hipóteses?")
  last = await evaluate("document.querySelector('.chat-message:last-child').innerText")
  assert.match(last, /Associações no bulário|Não encontrei fármacos/)
  await evaluate("localStorage.setItem('swine_auth', JSON.stringify({user:{id:'browser-isolated-user'}})); window.dispatchEvent(new Event('swine-auth-changed'))")
  await waitFor("document.querySelectorAll('.chat-message').length === 1")
  await evaluate("localStorage.removeItem('swine_auth'); window.dispatchEvent(new Event('swine-auth-changed'))")
  await waitFor("document.querySelectorAll('.chat-message').length > 1")
  await call("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await delay(300)
  assert.ok(await evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "A página excede a largura móvel")
  const screenshot = await call("Page.captureScreenshot", { format: "png" })
  const screenshotPath = process.env.SWINE_SCREENSHOT || join(tmpdir(), "swine-chat-mobile.png")
  await writeFile(screenshotPath, Buffer.from(screenshot.data, "base64"))
  await call("Page.navigate", { url: `${baseUrl}/bulario` })
  await waitFor("Boolean(document.querySelector('.package-card')) || document.body.innerText.includes('14 registros')")
  await evaluate("document.querySelector('.floating-compass__button').click()")
  await waitFor("Boolean(document.querySelector('.floating-compass__panel .clinical-context'))")
  await send("macho com tosse", true)
  assert.ok(await evaluate("document.querySelector('.floating-compass__messages').innerText.includes('Sinais confirmados: Tosse')"))
  assert.deepEqual(errors, [])
  console.log(`Chat, correções, dados estruturados, bulário, isolamento de contas e painel flutuante aprovados. Captura: ${screenshotPath}`)
} finally {
  socket?.close()
  chrome.kill()
  await new Promise((resolve) => { if (chrome.exitCode !== null) resolve(); else chrome.once("exit", resolve) })
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
}
