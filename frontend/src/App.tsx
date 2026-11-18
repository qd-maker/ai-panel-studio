import { useEffect, useState } from 'react'
import { api } from './api'
import DiscussionPage from './pages/DiscussionPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import { matchDiscussion, navigate, usePath } from './router'
import './App.css'

type Auth = 'checking' | 'ok' | 'login'

export default function App() {
  const path = usePath()
  const id = matchDiscussion(path)
  const [auth, setAuth] = useState<Auth>('checking')

  useEffect(() => {
    api
      .authStatus()
      .then((s) => setAuth(s.required && !s.authenticated ? 'login' : 'ok'))
      .catch(() => setAuth('ok')) // 状态接口不通时按无需登录处理，具体错误由页面自己展示
    const onUnauthorized = () => setAuth('login')
    window.addEventListener('aps:unauthorized', onUnauthorized)
    return () => window.removeEventListener('aps:unauthorized', onUnauthorized)
  }, [])

  return (
    <div className="app">
      <header className="app-bar">
        <a
          className="app-brand"
          href="/"
          onClick={(e) => {
            e.preventDefault()
            navigate('/')
          }}
        >
          AI 圆桌演播厅
        </a>
      </header>
      <main className="app-main">
        {auth === 'checking' ? null : auth === 'login' ? (
          <LoginPage onSuccess={() => setAuth('ok')} />
        ) : id ? (
          <DiscussionPage key={id} id={id} />
        ) : (
          <HomePage />
        )}
      </main>
    </div>
  )
}
