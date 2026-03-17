import { create } from 'zustand'

const STORAGE_KEY = 'allapi.userToken'

type AuthState = {
  token: string
  setToken: (token: string) => void
  logout: () => void
}

function loadToken(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function saveToken(token: string) {
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    return
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: loadToken(),
  setToken: (token) => {
    const t = token.trim()
    saveToken(t)
    set({ token: t })
  },
  logout: () => {
    saveToken('')
    set({ token: '' })
  },
}))

