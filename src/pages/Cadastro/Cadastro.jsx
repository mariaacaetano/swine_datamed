import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { User, Mail, Lock, ShieldCheck } from "lucide-react"
import { registerUser } from "../../services/auth"
import "./Cadastro.css"

function Cadastro() {
  const [nome, setNome] = useState("")
  const [email, setEmail] = useState("")
  const [senha, setSenha] = useState("")
  const [confirmacaoSenha, setConfirmacaoSenha] = useState("")
  const [message, setMessage] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible")
          }
        })
      },
      { threshold: 0.15 }
    )
    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el))

    let animationFrame = 0
    const current = { shift: 0, card: 0 }
    const target = { ...current }

    const measureScroll = () => {
      const page = document.querySelector(".cadastro-page")
      const viewport = window.innerHeight || 1
      const rect = page?.getBoundingClientRect()

      if (rect) {
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.shift = progress * 42
        target.card = progress * -10
      }
    }

    const render = () => {
      const page = document.querySelector(".cadastro-page")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (page) {
        page.style.setProperty("--auth-bg-shift", `${current.shift.toFixed(2)}px`)
        page.style.setProperty("--auth-card-shift", `${current.card.toFixed(2)}px`)
      }

      animationFrame = requestAnimationFrame(render)
    }

    measureScroll()
    render()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      observer.disconnect()
      cancelAnimationFrame(animationFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage("")

    if (senha !== confirmacaoSenha) {
      setMessage("As senhas nao conferem.")
      return
    }

    setIsSubmitting(true)

    try {
      const [firstName, ...lastNameParts] = nome.trim().split(/\s+/).filter(Boolean)

      await registerUser({
        email,
        password: senha,
        password_confirm: confirmacaoSenha,
        first_name: firstName || "",
        last_name: lastNameParts.join(" "),
      })
      navigate("/perfil")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="cadastro-page">
      <div className="cadastro-page__fade" aria-hidden="true" />
      <div className="cadastro-container">

        <div className="cadastro-brand reveal">
          <img src="/logos/pig_logo.png" alt="Swine DataMed" className="cadastro-logo" />
          <span className="cadastro-kicker">Swine DataMed</span>
          <h1>Crie sua conta</h1>
          <p>Configure seu acesso para explorar as ferramentas digitais da plataforma.</p>
        </div>

        <form className="cadastro-form" onSubmit={handleSubmit}>
          <h2 className="cadastro-title reveal">Cadastro</h2>

          <label className="cadastro-field reveal">
            <User size={16} className="cadastro-field-icon" />
            <input
              type="text"
              placeholder="Digite seu nome"
              className="cadastro-input"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              required
            />
          </label>

          <label className="cadastro-field reveal">
            <Mail size={16} className="cadastro-field-icon" />
            <input
              type="email"
              placeholder="Digite seu e-mail"
              className="cadastro-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="cadastro-field reveal">
            <Lock size={16} className="cadastro-field-icon" />
            <input
              type="password"
              placeholder="Digite sua senha"
              className="cadastro-input"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
          </label>

          <label className="cadastro-field reveal">
            <ShieldCheck size={16} className="cadastro-field-icon" />
            <input
              type="password"
              placeholder="Confirme sua senha"
              className="cadastro-input"
              value={confirmacaoSenha}
              onChange={(e) => setConfirmacaoSenha(e.target.value)}
              required
            />
          </label>

          <div className="cadastro-requisitos reveal">
            <p>Sua senha deve conter:</p>
            <ul>
              <li className={/[A-Z]/.test(senha) ? "ok" : ""}>Ao menos uma letra maiúscula</li>
              <li className={/[a-z]/.test(senha) ? "ok" : ""}>Ao menos uma letra minúscula</li>
              <li className={/[0-9]/.test(senha) ? "ok" : ""}>Ao menos um número</li>
              <li className={/[^A-Za-z0-9]/.test(senha) ? "ok" : ""}>Ao menos um caractere especial</li>
              <li>Caracteres permitidos: A-Z·0-9·@$%*#?&+-</li>
              <li className={senha.length >= 8 && senha.length <= 30 ? "ok" : ""}>Entre 8 e 30 caracteres</li>
            </ul>
          </div>

          {message && <p className="cadastro-message reveal">{message}</p>}

          <button className="cadastro-btn reveal" disabled={isSubmitting}>
            {isSubmitting ? "Cadastrando..." : "Cadastrar"}
          </button>

          <p className="cadastro-login reveal">
            Já tem uma conta?{" "}
            <Link to="/login">Faça Login.</Link>
          </p>
        </form>

      </div>
    </main>
  )
}

export default Cadastro
