import { useEffect } from "react"
import { Link, useLocation } from "react-router-dom"
import { Activity, ChevronRight, Pill } from "lucide-react"
import "./Home.css"

const frames = [
  {
    letter: "S",
    src: "/swine_pinterest/swine_01.jpg",
    alt: "Suíno no campo",
    title: "Sinais clínicos",
    text: "Observação visual para reconhecer alterações no comportamento e na saúde.",
  },
  {
    letter: "W",
    src: "/swine_pinterest/swine_02.jpg",
    alt: "Leitões na granja",
    title: "Bem-estar",
    text: "Acompanhamento do ambiente, manejo e fase produtiva dos animais.",
  },
  {
    letter: "I",
    src: "/swine_pinterest/swine_03.jpg",
    alt: "Suíno em ambiente rural",
    title: "Informação",
    text: "Dados organizados para consulta rápida durante a tomada de decisão.",
  },
  {
    letter: "N",
    src: "/swine_pinterest/swine_04.jpg",
    alt: "Suíno em manejo",
    title: "Nutrição e manejo",
    text: "Contexto produtivo conectado à avaliação sanitária da criação.",
  },
]

function Home() {
  const location = useLocation()

  useEffect(() => {
    const root = document.querySelector(".home")
    const revealEls = root ? [...root.querySelectorAll(".reveal")] : []
    let observer
    let animationFrame = 0
    let revealFrame = 0
    const current = {
      heroShift: 0,
      heroSwineShift: 0,
      heroDepthShift: 0,
      heroCopyShift: 0,
      heroFade: 0,
      stripShift: 0,
      frameShift1: 0,
      frameShift2: 0,
      frameShift3: 0,
      frameShift4: 0,
      textShift: 0,
    }
    const target = { ...current }

    const showVisibleReveals = () => {
      const viewport = window.innerHeight || 1
      revealEls.forEach((el) => {
        const rect = el.getBoundingClientRect()
        if (rect.top < viewport * 0.96 && rect.bottom > 0) el.classList.add("visible")
      })
    }

    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) entry.target.classList.add("visible")
          })
        },
        { threshold: 0.08, rootMargin: "0px 0px -8% 0px" }
      )

      revealEls.forEach((el) => observer.observe(el))
    } else {
      revealEls.forEach((el) => el.classList.add("visible"))
    }

    const measureScroll = () => {
      const hero = document.querySelector(".swine-hero")
      const nature = document.querySelector(".nature-section")
      const viewport = window.innerHeight || 1

      if (hero) {
        const rect = hero.getBoundingClientRect()
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.heroShift = progress * 42
        target.heroSwineShift = progress * -72
        target.heroDepthShift = progress * 28
        target.heroCopyShift = progress * -26
        target.heroFade = Math.max(0, progress) * 0.34
      }

      if (nature) {
        const rect = nature.getBoundingClientRect()
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.stripShift = progress * -46
        target.frameShift1 = progress * 12
        target.frameShift2 = progress * -18
        target.frameShift3 = progress * 16
        target.frameShift4 = progress * -10
        target.textShift = progress * 24
      }
    }

    const renderScrollEffects = () => {
      const hero = document.querySelector(".swine-hero")
      const nature = document.querySelector(".nature-section")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (hero) {
        hero.style.setProperty("--hero-shift", `${current.heroShift.toFixed(2)}px`)
        hero.style.setProperty("--hero-swine-shift", `${current.heroSwineShift.toFixed(2)}px`)
        hero.style.setProperty("--hero-depth-shift", `${current.heroDepthShift.toFixed(2)}px`)
        hero.style.setProperty("--hero-copy-shift", `${current.heroCopyShift.toFixed(2)}px`)
        hero.style.setProperty("--hero-fade", current.heroFade.toFixed(3))
      }

      if (nature) {
        nature.style.setProperty("--strip-shift", `${current.stripShift.toFixed(2)}px`)
        nature.style.setProperty("--frame-shift-1", `${current.frameShift1.toFixed(2)}px`)
        nature.style.setProperty("--frame-shift-2", `${current.frameShift2.toFixed(2)}px`)
        nature.style.setProperty("--frame-shift-3", `${current.frameShift3.toFixed(2)}px`)
        nature.style.setProperty("--frame-shift-4", `${current.frameShift4.toFixed(2)}px`)
        nature.style.setProperty("--text-shift", `${current.textShift.toFixed(2)}px`)
      }

      animationFrame = requestAnimationFrame(renderScrollEffects)
    }

    measureScroll()
    showVisibleReveals()
    revealFrame = requestAnimationFrame(showVisibleReveals)
    renderScrollEffects()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      observer?.disconnect()
      cancelAnimationFrame(animationFrame)
      cancelAnimationFrame(revealFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [location.key])

  return (
    <main className="home">
      <section className="swine-hero reveal" id="sobre">
        <div className="swine-hero__layer swine-hero__layer--fundo" aria-hidden="true" />
        <div className="swine-hero__layer swine-hero__layer--swine" aria-hidden="true" />
        <div className="swine-hero__depth" aria-hidden="true" />

        <div className="swine-hero__center">
          <span>Sistema especialista</span>
          <h1>Swine DataMed</h1>
          <p>
            Consulte medicamentos, observe sinais clínicos e organize decisões de manejo
            para suínos em uma experiência clara e visual.
          </p>
          <div className="swine-hero__actions" id="servicos">
            <Link to="/compass">
              <Activity size={20} />
              Analisar sintomas
              <ChevronRight size={20} />
            </Link>
            <Link to="/bulario">
              <Pill size={20} />
              Swine Package
            </Link>
          </div>
        </div>

        <div className="swine-hero__fade" aria-hidden="true" />
      </section>

      <section className="nature-section reveal" aria-label="Galeria Swine DataMed">
        <div className="nature-strip">
          {frames.map((frame, index) => (
            <figure className={`nature-frame nature-frame--${index + 1}`} key={frame.src}>
              <img src={frame.src} alt={frame.alt} />
              <figcaption>
                <span>{frame.letter}</span>
                <strong>{frame.title}</strong>
                <small>{frame.text}</small>
              </figcaption>
            </figure>
          ))}
        </div>

        <p>
          O Swine DataMed une Swine Package e apoio diagnóstico para ajudar produtores e
          profissionais a reconhecer sinais, consultar informações e conduzir decisões com
          mais segurança.
        </p>
      </section>
    </main>
  )
}

export default Home
