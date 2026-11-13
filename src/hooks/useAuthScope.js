import { useEffect, useState } from "react"
import { getAuth, onAuthChanged } from "../services/auth"

function currentScope() {
  const userId = getAuth()?.user?.id
  return userId ? `user-${userId}` : "guest"
}

export function useAuthScope() {
  const [scope, setScope] = useState(currentScope)
  useEffect(() => onAuthChanged(() => setScope(currentScope())), [])
  return scope
}
