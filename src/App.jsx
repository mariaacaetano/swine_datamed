import { useEffect } from "react"
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom"
import './App.css'

import Header from './components/Header/Header.jsx'
import FloatingCompass from './components/FloatingCompass/FloatingCompass.jsx'

import Home from "./pages/Home/Home.jsx"
import Login from "./pages/Login/Login.jsx"
import Cadastro from "./pages/Cadastro/Cadastro.jsx"
import RecuperarSenha from "./pages/RecuperarSenha/RecuperarSenha.jsx"
import Perfil from "./pages/Perfil/Perfil.jsx"
import Suinos from "./pages/Suinos/Suinos.jsx"
import Bulario from "./pages/Bulario/Bulario.jsx"
import Compass from "./pages/Compass/Compass.jsx"
import Servicos from "./pages/Servicos/Servicos.jsx"
import Calc from "./pages/Calc/Calc.jsx"
import Sobre from "./pages/Sobre/Sobre.jsx"
import Chat from "./pages/Chat/Chat.jsx"
import Error404 from "./pages/Erro/Erro404.jsx"

function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" })
  }, [pathname])

  return null
}

function FloatingCompassGate() {
  const { pathname } = useLocation()

  if (pathname === "/chat") return null

  return <FloatingCompass />
}

function VLibrasWidget() {
  useEffect(() => {
    const initWidget = () => {
      if (!window.VLibras?.Widget || window.__swineVLibrasInitialized) return

      new window.VLibras.Widget("https://vlibras.gov.br/app")
      window.__swineVLibrasInitialized = true
    }

    const scriptSrc = "https://vlibras.gov.br/app/vlibras-plugin.js"
    const existingScript = document.querySelector(`script[src="${scriptSrc}"]`)

    if (existingScript) {
      existingScript.addEventListener("load", initWidget)
      initWidget()

      return () => existingScript.removeEventListener("load", initWidget)
    }

    const script = document.createElement("script")
    script.src = scriptSrc
    script.async = true
    script.addEventListener("load", initWidget)
    document.body.appendChild(script)

    return () => script.removeEventListener("load", initWidget)
  }, [])

  return (
    <div vw="true" className="enabled">
      <div vw-access-button="true" className="active"></div>
      <div vw-plugin-wrapper="true">
        <div className="vw-plugin-top-wrapper"></div>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Header />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/cadastro" element={<Cadastro />} />
          <Route path="/recuperar-senha" element={<RecuperarSenha />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/suinos" element={<Suinos />} />
          <Route path="/suinos/:pigId" element={<Suinos />} />
          <Route path="/servicos" element={<Servicos />} />
          <Route path="/bulario" element={<Bulario />} />
          <Route path="/bulario/:slug" element={<Bulario />} />
          <Route path="/compass" element={<Compass />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/calc" element={<Calc />} />
          <Route path="/sobre" element={<Sobre />} />
          <Route path="*" element={<Error404 />} />
        </Routes>
      </main>
      <FloatingCompassGate />
      <VLibrasWidget />
    </BrowserRouter>
  )
}

export default App
