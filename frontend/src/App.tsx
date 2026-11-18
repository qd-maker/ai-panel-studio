import DiscussionPage from './pages/DiscussionPage'
import HomePage from './pages/HomePage'
import { matchDiscussion, navigate, usePath } from './router'
import './App.css'

export default function App() {
  const path = usePath()
  const id = matchDiscussion(path)

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
      <main className="app-main">{id ? <DiscussionPage key={id} id={id} /> : <HomePage />}</main>
    </div>
  )
}
