import { useEffect, useState } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { Calculator, ClipboardList, Compass, Home, MessageCircle, Pill, Search, User } from "lucide-react"
import { getAuth, onAuthChanged } from "../../services/auth"
import "./Header.css"

function Header() {
  const [expanded, setExpanded] = useState(false)
  const [auth, setAuth] = useState(getAuth)
  const navigate = useNavigate()
  const location = useLocation()
  const isCompass = location.pathname === "/compass"
  const profilePath = auth?.token ? "/perfil" : "/login"
  const displayName =
    auth?.user?.first_name ||
    auth?.user?.username ||
    auth?.user?.email ||
    "Perfil"

  useEffect(() => onAuthChanged(setAuth), [])

  const closeRail = () => setExpanded(false)

  const goHome = (e) => {
    e.preventDefault()
    navigate("/")
    closeRail()
    setTimeout(() => window.scrollTo({ top: 0, behavior: "smooth" }), 100)
  }

  return (
    <aside
      className={`side-rail ${expanded ? "rail-open" : ""} ${isCompass ? "side-rail-compass" : ""}`}
      aria-label="Menu lateral"
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      onFocus={() => setExpanded(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) closeRail()
      }}
    >
      <div className="rail-brand" aria-label="Swine DataMed">
        <img src="/logos/pig_logo.png" alt="" />
        {expanded && <span className="smooth-slide"><strong>Swine Datamed</strong></span>}
      </div>

      <nav className="rail-nav">
        <a className={location.pathname === "/" ? "rail-link rail-link-active" : "rail-link"} href="/" onClick={goHome} title="Home">
          <Home size={24} strokeWidth={1.7} />
          {expanded && <span className="smooth-slide">Home</span>}
        </a>
        <NavLink
          to="/servicos"
          className={({ isActive }) => (isActive ? "rail-link rail-link-active" : "rail-link")}
          onClick={closeRail}
          title="Serviços"
        >
          <Search size={24} strokeWidth={1.7} />
          {expanded && <span className="smooth-slide">Serviços</span>}
        </NavLink>
        <NavLink
          to="/bulario"
          className={({ isActive }) => (isActive ? "rail-link rail-link-active" : "rail-link")}
          onClick={closeRail}
          title="Swine Package"
        >
          <Pill size={24} strokeWidth={1.7} />
          {expanded && <span className="smooth-slide">Swine Package</span>}
        </NavLink>
        <NavLink
          to="/compass"
          className={({ isActive }) => (isActive ? "rail-link rail-link-active" : "rail-link")}
          onClick={closeRail}
          title="Swine Compass"
        >
          <Compass size={24} strokeWidth={1.7} />
          {expanded && <span className="smooth-slide">Swine Compass</span>}
        </NavLink>
        <NavLink
          to="/calc"
          className={({ isActive }) => (isActive ? "rail-link rail-link-active" : "rail-link")}
          onClick={closeRail}
          title="Swine Calc"
        >
          <Calculator size={24} strokeWidth={1.7} />
          {expanded && <span className="smooth-slide">Swine Calc</span>}
        </NavLink>
        {auth?.token && (
          <NavLink
            to="/suinos"
            className={({ isActive }) => (isActive ? "rail-link rail-link-active" : "rail-link")}
            onClick={closeRail}
            title="Suínos"
          >
            <ClipboardList size={24} strokeWidth={1.7} />
            {expanded && <span className="smooth-slide">Suínos</span>}
          </NavLink>
        )}
        <NavLink
          to="/sobre"
          className={({ isActive }) => (isActive ? "rail-link rail-link-active" : "rail-link")}
          onClick={closeRail}
          title="Sobre"
        >
          <MessageCircle size={24} strokeWidth={1.7} />
          {expanded && <span className="smooth-slide">Sobre</span>}
        </NavLink>
      </nav>

      <div className="rail-user">
        <NavLink
          to={profilePath}
          className={({ isActive }) => (isActive ? "rail-profile rail-profile-active" : "rail-profile")}
          onClick={closeRail}
          title={auth?.token ? "Meu perfil" : "Log in"}
        >
          <span className="rail-avatar">
            <User size={18} strokeWidth={1.7} />
          </span>
          {expanded && (
            <span className="rail-user-text smooth-slide">
              <strong>{auth?.token ? displayName : "Log in"}</strong>
              <small>{auth?.token ? "Meu perfil" : "Criar conta"}</small>
            </span>
          )}
        </NavLink>
      </div>
    </aside>
  )
}

export default Header
