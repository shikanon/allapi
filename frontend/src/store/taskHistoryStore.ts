import { create } from 'zustand'

const STORAGE_KEY = 'allapi.taskHistory.v1'

type TaskHistoryState = {
  byToken: Record<string, string[]>
  addTask: (token: string, taskId: string) => void
  removeTask: (token: string, taskId: string) => void
  clearToken: (token: string) => void
}

function safeParse(jsonText: string): unknown {
  try {
    return JSON.parse(jsonText)
  } catch {
    return null
  }
}

function load(): Record<string, string[]> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const obj = safeParse(raw)
    if (!obj || typeof obj !== 'object') return {}

    const out: Record<string, string[]> = {}
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      if (typeof k !== 'string') continue
      if (!Array.isArray(v)) continue
      out[k] = v.filter((x) => typeof x === 'string') as string[]
    }
    return out
  } catch {
    return {}
  }
}

function save(byToken: Record<string, string[]>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(byToken))
  } catch {
    return
  }
}

export const useTaskHistoryStore = create<TaskHistoryState>((set, get) => ({
  byToken: load(),
  addTask: (token, taskId) => {
    const t = token.trim()
    const id = taskId.trim()
    if (!t || !id) return

    const byToken = { ...get().byToken }
    const list = byToken[t] ? [...byToken[t]] : []
    if (!list.includes(id)) list.unshift(id)
    byToken[t] = list.slice(0, 50)
    save(byToken)
    set({ byToken })
  },
  removeTask: (token, taskId) => {
    const t = token.trim()
    const id = taskId.trim()
    if (!t || !id) return

    const byToken = { ...get().byToken }
    byToken[t] = (byToken[t] ?? []).filter((x) => x !== id)
    save(byToken)
    set({ byToken })
  },
  clearToken: (token) => {
    const t = token.trim()
    if (!t) return
    const byToken = { ...get().byToken }
    delete byToken[t]
    save(byToken)
    set({ byToken })
  },
}))

