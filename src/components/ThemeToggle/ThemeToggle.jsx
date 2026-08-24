import { Moon, Sun } from "lucide-react"
import { useLayoutEffect, useState } from "react"
import "./ThemeToggle.css"

const storageKey = "swine-color-theme"

function readTheme() {
  return localStorage.getItem(storageKey) === "dark" ? "dark" : "light"
}

function ThemeToggle() {
  const [theme, setTheme] = useState(readTheme)

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    localStorage.setItem(storageKey, theme)
  }, [theme])

  const dark = theme === "dark"

  return (
    <div className="theme-toggle" role="group" aria-label="Tema da interface">
      <button
        type="button"
        className={!dark ? "is-active" : ""}
        aria-pressed={!dark}
        onClick={() => setTheme("light")}
        title="Usar tema claro"
      >
        <Sun size={16} aria-hidden="true" />
        <span>Light</span>
      </button>
      <button
        type="button"
        className={dark ? "is-active" : ""}
        aria-pressed={dark}
        onClick={() => setTheme("dark")}
        title="Usar tema escuro"
      >
        <Moon size={16} aria-hidden="true" />
        <span>Dark</span>
      </button>
    </div>
  )
}

export default ThemeToggle
