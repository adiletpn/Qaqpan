import type { ReactNode } from 'react'

const paths: Record<string, string> = {
  shield: 'M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z',
  check: 'M5 12.5 10 17l9-10',
  x: 'M6 6l12 12M18 6 6 18',
  alert: 'M12 3 2 20h20L12 3Zm0 6v5m0 3v.5',
  phone: 'M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2Z',
  msg: 'M4 4h16v12H8l-4 4V4Z',
  send: 'M4 12 20 4l-6 16-3-7-7-1Z',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-2.5-11.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14m0 3v.5',
  back: 'M15 5l-7 7 7 7',
  family: 'M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 20c0-3.3 2.7-6 6-6s6 2.7 6 6M14 14.3c.6-.2 1.3-.3 2-.3 3.3 0 6 2.7 6 6',
  news: 'M4 5h13v14H6a2 2 0 0 1-2-2V5Zm13 4h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5',
  image: 'M4 5h16v14H4V5Zm0 10 4-4 4 4 3-3 5 5M15 9.5v.5',
}

export function Icon({ name, className = 'w-5 h-5' }: { name: keyof typeof paths | string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d={paths[name] ?? paths.help} />
    </svg>
  )
}

type Tone = 'primary' | 'danger' | 'ghost' | 'light' | 'success'
const tones: Record<Tone, string> = {
  primary: 'bg-teal-700 text-white active:bg-teal-800',
  danger: 'bg-red-600 text-white active:bg-red-700',
  success: 'bg-emerald-600 text-white active:bg-emerald-700',
  ghost: 'bg-transparent text-teal-800 active:bg-teal-50',
  light: 'bg-white text-slate-800 border border-slate-200 active:bg-slate-50',
}

export function Button({ children, onClick, tone = 'primary', disabled, className = '' }: {
  children: ReactNode; onClick?: () => void; tone?: Tone; disabled?: boolean; className?: string
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`w-full rounded-2xl px-4 py-3.5 text-[15px] font-semibold transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100 ${tones[tone]} ${className}`}>
      {children}
    </button>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100 ${className}`}>{children}</div>
}

export function Header({ title, onBack }: { title: string; onBack?: () => void }) {
  return (
    <div className="sticky top-0 z-10 flex items-center gap-2 bg-slate-50/95 px-4 pb-3 pt-2 backdrop-blur">
      {onBack && (
        <button onClick={onBack} className="-ml-2 rounded-full p-2 text-slate-700 transition active:scale-90 active:bg-slate-200" aria-label="back">
          <Icon name="back" />
        </button>
      )}
      <h2 className="text-lg font-bold text-slate-900">{title}</h2>
    </div>
  )
}

export function Spinner() {
  return <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
}
