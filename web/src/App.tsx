import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import BankApp from './phone/BankApp'
import Director from './pages/Director'
import Stage from './pages/Stage'
import { Icon } from './ui'

// /phone/:id — the app full-screen on a real phone (open the link on any device, or add it to the home screen)
function PhonePage() {
  const { id = 'aigerim' } = useParams()
  return (
    <div className="min-h-[100dvh] bg-slate-50">
      <div className="mx-auto h-[100dvh] max-w-md pt-[env(safe-area-inset-top)]"><BankApp clientId={id} /></div>
    </div>
  )
}

const LAYERS = [
  { n: 1, step: 'Написали', title: 'Проверка сообщений', text: 'SMS, ссылка или скриншот — ответ за секунду на русском или казахском: мошенничество или нет и почему.', icon: 'msg' },
  { n: 2, step: 'Позвонили', title: '«Банк мне звонит?»', text: 'Номер можно подделать, журнал звонков банка — нет. Одна кнопка во время звонка.', icon: 'phone' },
  { n: 3, step: 'Уговорили перевести', title: 'Умный перевод и семейный щит', text: 'Звонок + новый получатель + почти все деньги → пауза и вопросы. Крупный перевод ждёт ответа близкого.', icon: 'family' },
  { n: 4, step: 'Получили деньги', title: 'Сеть защиты', text: 'Жалоба на остановленный перевод — и все, кто переводит на этот счёт, получают паузу и вопросы.', icon: 'shield' },
]

function Index() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-5xl px-6 py-12 md:py-16">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-emerald-500"><Icon name="shield" className="h-7 w-7" /></div>
        </div>
        <h1 className="mt-6 text-5xl font-black tracking-tight md:text-6xl">Qaqpan</h1>
        <p className="mt-3 max-w-2xl text-xl text-slate-300">Капкан для мошенников внутри приложения банка.</p>
        <p className="mt-2 max-w-2xl text-slate-400">
          Любое мошенничество проходит четыре шага. На каждом стоит слой защиты, и слои передают сигнал друг другу:
          то, что пропустил один, ловит следующий.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/stage" className="rounded-2xl bg-emerald-500 px-5 py-3 font-semibold text-white hover:bg-emerald-400">Посмотреть, как работает ›</Link>
          <Link to="/phone/aigerim" className="rounded-2xl bg-white/10 px-5 py-3 font-semibold ring-1 ring-white/15 hover:bg-white/15">Приложение на телефоне</Link>
        </div>

        <div className="mt-12 grid gap-3 md:grid-cols-2">
          {LAYERS.map(l => (
            <div key={l.n} className="rounded-3xl bg-white/[0.04] p-5 ring-1 ring-white/10">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-500/15 text-emerald-300"><Icon name={l.icon} /></span>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Шаг {l.n} · {l.step}</div>
                  <div className="font-bold">{l.title}</div>
                </div>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">{l.text}</p>
            </div>
          ))}
        </div>

        <div className="mt-10 grid gap-2 text-sm md:grid-cols-3">
          {[['/phone/aigerim', 'Айгерим, 52', 'клиентка банка'], ['/phone/erzhan', 'Ержан, 27', 'сын · доверенное лицо'], ['/phone/madina', 'Мадина, 34', 'другая клиентка']].map(([to, name, role]) => (
            <Link key={to} to={to} className="rounded-2xl bg-white/[0.03] p-4 ring-1 ring-white/10 hover:bg-white/[0.06]">
              <div className="font-semibold">{name}</div><div className="text-slate-500">{role}</div>
            </Link>
          ))}
        </div>

        <p className="mt-10 text-xs text-slate-600">
          Клиенты, счета и звонки вымышленные.
        </p>
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
