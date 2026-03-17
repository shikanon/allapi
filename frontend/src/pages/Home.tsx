import { Navigate } from 'react-router-dom'

import { useAuthStore } from '@/store/authStore'

export default function Home() {
  const token = useAuthStore((s) => s.token)
  return <Navigate to={token ? '/console' : '/login'} replace />
}
