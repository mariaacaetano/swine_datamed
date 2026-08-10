import { ArrowLeft, Home, SearchX } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import "./Erro404.css"

export default function Error404() {
  const navigate = useNavigate()

  return (
    <main className="error-page">
      <section className="error-shell">
        <div className="error-copy">
          <span className="error-kicker">Erro 404</span>
          <h1>Página não encontrada</h1>
          <p>O endereço acessado não existe ou foi movido. Volte para uma área conhecida da plataforma para continuar.</p>

          <div className="error-actions">
            <button type="button" className="error-secondary" onClick={() => navigate(-1)}>
              <ArrowLeft size={18} strokeWidth={1.8} />
              Voltar
            </button>
            <Link to="/" className="error-primary">
              <Home size={18} strokeWidth={1.8} />
              Início
            </Link>
          </div>
        </div>

        <div className="error-visual" aria-hidden="true">
          <img src="/swine_pinterest/pig_error.jpg" alt="" />
          <div>
            <SearchX size={34} strokeWidth={1.6} />
            <strong>404</strong>
          </div>
        </div>
      </section>
    </main>
  )
}
