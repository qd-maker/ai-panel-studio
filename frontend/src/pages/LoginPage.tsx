// 线上演示站的访问密码页。后端设置了 APP_PASSWORD 时才会出现。

import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiFailure } from '../api'
import './LoginPage.css'

export default function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!password || busy) return
    setBusy(true)
    setError(null)
    try {
      await api.login(password)
      onSuccess()
    } catch (err) {
      setError(err instanceof ApiFailure ? err.message : '登录失败，请重试')
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <form className="login-card" onSubmit={submit}>
        <span className="login-dot" aria-hidden="true" />
        <h1 className="login-title">AI 圆桌演播厅</h1>
        <p className="login-lead">这是一个演示站，每场讨论都会调用真实的大模型。请输入访问密码。</p>
        <label className="login-label" htmlFor="password">
          访问密码
        </label>
        <input
          id="password"
          className="login-input"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary login-submit" disabled={!password || busy}>
          {busy ? '正在进入⋯⋯' : '进入演播厅'}
        </button>
      </form>
    </div>
  )
}
