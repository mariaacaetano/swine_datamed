import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { KeyRound, Lock, Mail, ShieldCheck } from "lucide-react"
import { confirmPasswordReset, requestPasswordReset } from "../../services/auth"
import "../Login/Login.css"

function RecuperarSenha() {
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [password, setPassword] = useState("")
  const [passwordConfirm, setPasswordConfirm] = useState("")
  const [step, setStep] = useState("request")
  const [message, setMessage] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleRequestCode = async (event) => {
    event.preventDefault()
    setMessage("")
    setIsSubmitting(true)

    try {
      const response = await requestPasswordReset({ email })
      setMessage(response.detail)
      setStep("confirm")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleConfirmReset = async (event) => {
    event.preventDefault()
    setMessage("")

    if (password !== passwordConfirm) {
      setMessage("As senhas nao conferem.")
      return
    }

    setIsSubmitting(true)

    try {
      const response = await confirmPasswordReset({
        email,
        code,
        password,
        password_confirm: passwordConfirm,
      })
      setMessage(response.detail)
      window.setTimeout(() => navigate("/login"), 900)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-page__fade" aria-hidden="true" />
      <div className="login-container">
        <div className="login-brand reveal visible">
          <img src="/logos/pig_logo.png" alt="Swine DataMed" className="login-logo" />
          <span className="login-kicker">Swine DataMed</span>
          <h1>Recupere sua senha</h1>
          <p>Informe seu e-mail para receber um código de segurança e cadastrar uma nova senha.</p>
        </div>

        {step === "request" ? (
          <form className="login-form" onSubmit={handleRequestCode}>
            <h2 className="login-title reveal visible">Enviar código</h2>

            <label className="login-field reveal visible">
              <Mail size={16} className="login-field-icon" />
              <input
                type="email"
                placeholder="Digite seu e-mail"
                className="login-input"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>

            {message && <p className="login-message reveal visible">{message}</p>}

            <button className="login-btn reveal visible" disabled={isSubmitting}>
              {isSubmitting ? "Enviando..." : "Receber código"}
            </button>

            <p className="login-register reveal visible">
              Lembrou sua senha? <Link to="/login">Voltar ao login.</Link>
            </p>
          </form>
        ) : (
          <form className="login-form" onSubmit={handleConfirmReset}>
            <h2 className="login-title reveal visible">Nova senha</h2>

            <label className="login-field reveal visible">
              <ShieldCheck size={16} className="login-field-icon" />
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="Código de 6 dígitos"
                className="login-input"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                required
              />
            </label>

            <label className="login-field reveal visible">
              <Lock size={16} className="login-field-icon" />
              <input
                type="password"
                placeholder="Digite a nova senha"
                className="login-input"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>

            <label className="login-field reveal visible">
              <KeyRound size={16} className="login-field-icon" />
              <input
                type="password"
                placeholder="Confirme a nova senha"
                className="login-input"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                required
              />
            </label>

            {message && <p className="login-message reveal visible">{message}</p>}

            <button className="login-btn reveal visible" disabled={isSubmitting}>
              {isSubmitting ? "Salvando..." : "Redefinir senha"}
            </button>

            <p className="login-register reveal visible">
              Não recebeu?{" "}
              <button type="button" className="login-inline-action" onClick={() => setStep("request")}>
                Enviar outro código.
              </button>
            </p>
          </form>
        )}
      </div>
    </main>
  )
}

export default RecuperarSenha
