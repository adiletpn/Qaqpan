import { motion } from 'framer-motion'
import { useState } from 'react'
import { guardianLink, useBot, useQr } from './telegram-hooks'
import { Icon } from './ui'

// Laptop: a small card with the QR — scan it with the phone
export function TelegramCard({ sandbox }: { sandbox: string | null }) {
  const bot = useBot()
  const link = bot ? guardianLink(bot, sandbox) : null
  const qr = useQr(link, 240)
  const [open, setOpen] = useState(true)
  if (!bot || !link) return null
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="fixed bottom-5 left-5 z-40 w-[250px] rounded-3xl bg-white/95 p-4 text-slate-900 shadow-2xl ring-1 ring-black/5 backdrop-blur">
      <button onClick={() => setOpen(o => !o)} className="flex w-full items-center gap-2 text-left">
        <span className="grid h-8 w-8 place-items-center rounded-xl bg-sky-500 text-white"><Icon name="send" className="h-4 w-4" /></span>
        <span className="text-sm font-bold leading-tight">Станьте сыном<br /><span className="text-xs font-normal text-slate-500">в своём Telegram</span></span>
        <span className="ml-auto text-slate-400">{open ? '–' : '+'}</span>
      </button>
      {open && (
        <div className="mt-3">
          {qr && <img src={qr} alt="QR" className="mx-auto h-[180px] w-[180px] rounded-xl" />}
          <p className="mt-2 text-xs leading-relaxed text-slate-500">Отсканируйте телефоном — уведомление «Маму, возможно, обманывают» придёт вам, и вы сами нажмёте «Отклонить».</p>
          <a href={link} target="_blank" rel="noreferrer" className="mt-2 block text-center text-xs font-semibold text-sky-600">@{bot}</a>
        </div>
      )}
    </motion.div>
  )
}

// Phone: a button that opens Telegram
export function TelegramButton({ sandbox, className = '' }: { sandbox: string | null; className?: string }) {
  const bot = useBot()
  if (!bot) return null
  return (
    <a href={guardianLink(bot, sandbox)} target="_blank" rel="noreferrer"
      className={`flex items-center justify-center gap-2 rounded-2xl bg-sky-500 px-4 py-2.5 text-sm font-semibold text-white active:scale-[0.97] ${className}`}>
      <Icon name="send" className="h-4 w-4" />Уведомления сына — в мой Telegram
    </a>
  )
}

// Stage: a big QR for the jury (hotkey Q)
export function StageQr({ onClose }: { onClose: () => void }) {
  const bot = useBot()
  const link = bot ? guardianLink(bot, null) : null
  const qr = useQr(link, 520)
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}
      className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/80 backdrop-blur">
      <div className="rounded-[36px] bg-white p-8 text-center text-slate-900 shadow-2xl">
        {qr ? <img src={qr} alt="QR" className="mx-auto h-[360px] w-[360px]" /> : <div className="h-[360px] w-[360px] text-slate-400">Бот не подключён</div>}
        <div className="mt-4 text-2xl font-black">Станьте сыном Айгерим</div>
        <div className="mt-1 text-slate-500">Отсканируйте — уведомление придёт в ваш Telegram{bot ? ` · @${bot}` : ''}</div>
      </div>
    </motion.div>
  )
}
