import { create } from 'zustand'

export type DebugLogEntry = {
  id: string
  createdAt: number
  method: string
  path: string
  status: number | null
  durationMs: number
  ok: boolean
  requestBody: string
  responseBody: string
  errorMessage: string
}

type DebugLogState = {
  entries: DebugLogEntry[]
  selectedId: string | null
  add: (entry: DebugLogEntry) => void
  clear: () => void
  select: (id: string | null) => void
}

export const useDebugLogStore = create<DebugLogState>((set, get) => ({
  entries: [],
  selectedId: null,
  add: (entry) => {
    const next = [entry, ...get().entries].slice(0, 50)
    set({ entries: next, selectedId: entry.id })
  },
  clear: () => set({ entries: [], selectedId: null }),
  select: (id) => set({ selectedId: id }),
}))

