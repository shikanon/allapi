import { LogOut } from 'lucide-react'

import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/Button'

function maskToken(token: string) {
  const t = token.trim()
  if (!t) return ''
  if (t.length <= 12) return `${t.slice(0, 4)}…${t.slice(-2)}`
  return `${t.slice(0, 6)}…${t.slice(-4)}`
}

export function TopNav({ onLogout }: { onLogout: () => void }) {
  const token = useAuthStore((s) => s.token)

  return (
    <div className="sticky top-0 z-40 border-b border-white/10 bg-[#0B1220]/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="text-sm font-semibold text-white">视频任务控制台</div>
          <div className="hidden text-xs text-white/50 md:block">
            Token：{maskToken(token)}
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={onLogout}>
          <LogOut className="h-4 w-4" />
          退出登录
        </Button>
      </div>
    </div>
  )
}

