import { requestJson } from "./api"
export { requestJson } from "./api"
const AUTH_STORAGE_KEY = "swine_auth"
const AUTH_CHANGED_EVENT = "swine-auth-changed"

function parseAuthStorage() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || "null")
  } catch {
    return null
  }
}

function notifyAuthChanged() {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
}

export function getAuth() {
  return parseAuthStorage()
}

export function getAuthToken() {
  return parseAuthStorage()?.token || ""
}

export function isAuthenticated() {
  return Boolean(getAuthToken())
}

export function saveAuth(authData) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authData))
  notifyAuthChanged()
}

export function clearAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY)
  notifyAuthChanged()
}

export function onAuthChanged(callback) {
  const handler = () => callback(getAuth())
  window.addEventListener(AUTH_CHANGED_EVENT, handler)
  window.addEventListener("storage", handler)

  return () => {
    window.removeEventListener(AUTH_CHANGED_EVENT, handler)
    window.removeEventListener("storage", handler)
  }
}

export async function loginUser(credentials) {
  const authData = await requestJson("/auth/login/", {
    method: "POST",
    body: JSON.stringify(credentials),
  })
  saveAuth(authData)
  return authData
}

export async function registerUser(payload) {
  const authData = await requestJson("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
  saveAuth(authData)
  return authData
}

export async function requestPasswordReset(payload) {
  return requestJson("/auth/password-reset/request/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function confirmPasswordReset(payload) {
  return requestJson("/auth/password-reset/confirm/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function getCurrentUser() {
  return requestJson("/auth/me/", {
    headers: {
      Authorization: `Token ${getAuthToken()}`,
    },
  })
}

export async function updateCurrentUser(payload) {
  const updatedUser = await requestJson("/auth/me/", {
    method: "PATCH",
    headers: {
      Authorization: `Token ${getAuthToken()}`,
    },
    body: payload instanceof FormData ? payload : JSON.stringify(payload),
  })
  saveAuth({ token: getAuthToken(), user: updatedUser })
  return updatedUser
}

export async function logoutUser() {
  const token = getAuthToken()

  if (token) {
    await requestJson("/auth/logout/", {
      method: "POST",
      headers: {
        Authorization: `Token ${token}`,
      },
    }).catch(() => null)
  }

  clearAuth()
}
