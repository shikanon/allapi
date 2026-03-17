import { Eye, EyeOff } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuthStore } from '@/store/authStore'

export default function Login() {
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.token)
  const setToken = useAuthStore((s) => s.setToken)
  const logout = useAuthStore((s) => s.logout)

  const [value, setValue] = useState('')
  const [visible, setVisible] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canSubmit = useMemo(() => value.trim().length > 0, [value])

  async function verifyToken(inputToken: string) {
    const resp = await fetch('/v1/usage?limit=1', {
      headers: {
        Authorization: `Bearer ${inputToken}`,
      },
    })
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(text || `${resp.status} ${resp.statusText}`)
    }
  }

  async function onLogin() {
    setError('')
    const t = value.trim()
    if (!t) return
    setLoading(true)
    try {
      await verifyToken(t)
      setToken(t)
      navigate('/console', { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B1220]">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg">
          <div className="mb-6 text-center">
            <div className="text-sm font-semibold text-white">视频任务控制台</div>
            <div className="mt-2 text-sm text-white/70">
              使用 Token 登录，查看用量记录与计费报价，并调试视频任务 API。
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Token 登录</CardTitle>
              <CardDescription>Token 仅保存在你的浏览器本地，可随时退出清除。</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="mb-2 text-xs text-white/70">用户 Token</div>
                  <div className="relative">
                    <Input
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      placeholder="粘贴你的 Token"
                      type={visible ? 'text' : 'password'}
                      autoComplete="off"
                    />
                    <button
                      type="button"
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-white/60 hover:bg-white/5 hover:text-white"
                      onClick={() => setVisible((v) => !v)}
                    >
                      {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {error ? (
                    <div className="mt-2 text-sm text-red-400">{error}</div>
                  ) : null}
                </div>

                <div className="flex items-center gap-3">
                  <Button loading={loading} onClick={onLogin} disabled={!canSubmit}>
                    登录
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setValue('')
                      setError('')
                    }}
                    type="button"
                  >
                    清空
                  </Button>
                </div>

                {token ? (
                  <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <div className="text-sm font-medium text-white">检测到已保存 Token</div>
                    <div className="mt-1 text-sm text-white/70">
                      你可以直接进入控制台，或退出清除本地 Token。
                    </div>
                    <div className="mt-3 flex items-center gap-3">
                      <Button
                        variant="secondary"
                        onClick={() => navigate('/console', { replace: true })}
                      >
                        进入控制台
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          logout()
                          setValue('')
                        }}
                      >
                        退出/清除 Token
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

