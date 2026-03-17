import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { TopNav } from '@/components/layout/TopNav'
import { Tabs } from '@/components/ui/Tabs'
import { BillingPanel } from '@/features/billing/BillingPanel'
import { RequestLogPanel } from '@/features/logs/RequestLogPanel'
import { UsagePanel } from '@/features/usage/UsagePanel'
import { VideoDebugPanel } from '@/features/video/VideoDebugPanel'
import { useAuthStore } from '@/store/authStore'

type TabKey = 'usage' | 'billing' | 'video' | 'logs'

export default function Console() {
  const navigate = useNavigate()
  const logout = useAuthStore((s) => s.logout)
  const [tab, setTab] = useState<TabKey>('usage')

  useEffect(() => {
    document.title = '控制台 - 视频任务控制台'
  }, [])

  return (
    <div className="min-h-screen bg-[#0B1220]">
      <TopNav
        onLogout={() => {
          logout()
          navigate('/login', { replace: true })
        }}
      />

      <AppShell
        title="控制台"
        subtitle="查看用量记录与计费报价，并调试创建/查询/取消视频任务。"
      >
        <div className="mb-4">
          <Tabs<TabKey>
            value={tab}
            onChange={setTab}
            items={[
              { key: 'usage', label: '用量记录' },
              { key: 'billing', label: '计费报价' },
              { key: 'video', label: '视频任务调试' },
              { key: 'logs', label: '请求日志' },
            ]}
          />
        </div>

        {tab === 'usage' ? <UsagePanel /> : null}
        {tab === 'billing' ? <BillingPanel /> : null}
        {tab === 'video' ? <VideoDebugPanel /> : null}
        {tab === 'logs' ? <RequestLogPanel /> : null}
      </AppShell>
    </div>
  )
}

