import { getAuthToken, requestJson } from "./auth"
import { requestCollection } from "./api"

function authHeaders() {
  return {
    Authorization: `Token ${getAuthToken()}`,
  }
}

export function listPigs() {
  return requestCollection("/suinos/", {
    headers: authHeaders(),
  })
}

export function createPig(payload) {
  return requestJson("/suinos/", {
    method: "POST",
    headers: authHeaders(),
    body: payload instanceof FormData ? payload : JSON.stringify(payload),
  })
}

export function updatePig(id, payload) {
  return requestJson(`/suinos/${id}/`, {
    method: "PATCH",
    headers: authHeaders(),
    body: payload instanceof FormData ? payload : JSON.stringify(payload),
  })
}

export function deletePig(id) {
  return requestJson(`/suinos/${id}/`, {
    method: "DELETE",
    headers: authHeaders(),
  })
}

export function listMedications(pigId = "") {
  const query = pigId ? `?pig=${pigId}` : ""
  return requestCollection(`/medicacoes/${query}`, {
    headers: authHeaders(),
  })
}

export function createMedication(payload) {
  return requestJson("/medicacoes/", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  })
}
