import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import BankApp from './phone/BankApp'
import Director from './pages/Director'
import Stage from './pages/Stage'

// /phone/:id — the app full-screen on a real phone (open the link on any device)
function PhonePage() {
  const { id = 'aigerim' } = useParams()
  return <div className="mx-auto h-[100dvh] max-w-md"><BankApp clientId={id} /></div>
}

function Index() {
  const links = [
    ['/stage', 'Сцена', 'три телефона + 4 шага, для проектора'],
    ['/director', 'Пульт', 'кнопки сценария и горячие клавиши'],
    ['/phone/aigerim', 'Телефон Айгерим', 'открыть на настоящем телефоне'],
    ['/phone/erzhan', 'Телефон Ержана', 'доверенное лицо'],
    ['/phone/madina', 'Телефон Мадины', 'другой клиент'],
  ]
  return (
    <div className="min-h-screen bg-slate-950 p-8 text-white">
      <h1 className="text-3xl font-black">Qaqpan</h1>
      <p className="mt-1 text-slate-400">Прототип модуля защиты от мошенников для приложения банка · ITU Hackathon 2026</p>
      <div className="mt-6 grid max-w-xl gap-2">
        {links.map(([to, title, hint]) => (
          <Link key={to} to={to} className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10 hover:bg-white/10">
            <div className="font-semibold">{title}</div><div className="text-sm text-slate-400">{hint}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/stage" element={<Stage />} />
        <Route path="/director" element={<Director />} />
        <Route path="/phone/:id" element={<PhonePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
