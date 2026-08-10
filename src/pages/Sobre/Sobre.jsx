import { useEffect } from "react"
import { BrainCircuit, Database, GraduationCap, HeartPulse, Pill, ShieldCheck } from "lucide-react"
import "./Sobre.css"

const topics = [
  { icon: HeartPulse, label: "Sanidade", text: "Apoio à avaliação clínica e ao manejo sanitário." },
  { icon: Database, label: "Dados", text: "Relações entre sintomas, ambiente, histórico e produção." },
  { icon: Pill, label: "Bulário", text: "Informações farmacológicas para consulta responsável." },
]

function Sobre() {
  useEffect(() => {
    let animationFrame = 0
    const current = { hero: 0, image: 0, text: 0 }
    const target = { ...current }

    const measureScroll = () => {
      const page = document.querySelector(".about-page")
      const hero = document.querySelector(".about-hero")
      const viewport = window.innerHeight || 1

      if (hero) {
        const rect = hero.getBoundingClientRect()
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.hero = progress * 52
        target.image = progress * -28
        target.text = progress * 18
      }

      page?.style.setProperty("--about-ready", "1")
    }

    const render = () => {
      const page = document.querySelector(".about-page")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (page) {
        page.style.setProperty("--about-hero-shift", `${current.hero.toFixed(2)}px`)
        page.style.setProperty("--about-image-shift", `${current.image.toFixed(2)}px`)
        page.style.setProperty("--about-text-shift", `${current.text.toFixed(2)}px`)
      }

      animationFrame = requestAnimationFrame(render)
    }

    measureScroll()
    render()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      cancelAnimationFrame(animationFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [])

  return (
    <main className="about-page">
      <section className="about-hero">
        <div className="about-hero__content">
          <span>Sobre o projeto</span>
          <h1>Swine DataMed</h1>
          <p>
            Tecnologia aplicada à sanidade animal. Dados transformados em decisão.
          </p>
        </div>
      </section>

      <section className="about-body">
        <aside className="about-side">
          <div className="about-photo">
            <img src="/swine_pinterest/swine_02.jpg" alt="Suínos em granja" />
          </div>
          <div className="about-author">
            <GraduationCap size={30} />
            <div>
              <p>
                Maria Fernanda Caetano, graduanda de Bacharelado em Sistemas de Informação
                pelo Instituto Federal Catarinense, Campus Araquari.
              </p>
              <p>Maithê Alves Borba, graduanda de Bacharelado em Medicina Veterinária
                pelo Instituto Federal Catarinense, Campus Araquari.</p>
            </div>
          </div>
        </aside>

        <article className="about-text">
          <p>
            O Swine DataMed é uma plataforma inteligente desenvolvida com foco em
            sanidade e manejo na suinocultura, criada para auxiliar produtores,
            médicos-veterinários e profissionais do setor na avaliação de doenças,
            análise clínica e apoio à tomada de decisão.
          </p>
          <p>
            O sistema integra informações técnicas sobre sintomas, doenças suínas,
            medicamentos veterinários, protocolos terapêuticos, fatores ambientais e
            indicadores produtivos, centralizando dados importantes em uma única
            plataforma digital.
          </p>
          <p>
            A solução utiliza uma abordagem baseada em relações entre dados clínicos e
            epidemiológicos, permitindo correlacionar características como sinais
            clínicos, fase produtiva dos animais, condições ambientais, histórico
            sanitário e tratamentos disponíveis, contribuindo para uma avaliação mais
            rápida e estruturada.
          </p>
          <p>
            Além disso, o Swine DataMed incorpora um bulário veterinário digital
            inteligente, reunindo informações farmacológicas, mecanismos de ação,
            contraindicações, períodos de carência, vias de administração e
            recomendações de uso de medicamentos voltados para a produção suína.
          </p>
          <p>
            Desenvolvido como projeto acadêmico e tecnológico, o Swine DataMed busca
            unir tecnologia, ciência de dados e medicina veterinária, contribuindo para
            a modernização da gestão sanitária na suinocultura e para o fortalecimento
            de práticas baseadas em informação e análise de dados.
          </p>
        </article>
      </section>

      <section className="about-topics" aria-label="Pilares do Swiner DataMed">
        {topics.map(({ icon: Icon, label, text }) => (
          <article key={label}>
            <Icon size={32} />
            <strong>{label}</strong>
            <p>{text}</p>
          </article>
        ))}
        <article>
          <BrainCircuit size={32} />
          <strong>Inteligência</strong>
          <p>Dados clínicos e epidemiológicos conectados para estruturar análise.</p>
        </article>
        <article>
          <ShieldCheck size={32} />
          <strong>Decisão</strong>
          <p>Informação organizada para apoiar escolhas técnicas com segurança.</p>
        </article>
      </section>
    </main>
  )
}

export default Sobre
