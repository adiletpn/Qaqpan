import { useEffect, useState, type ReactNode } from 'react'

// iPhone 15-like device mockup in pure CSS: titanium frame, side buttons, Dynamic Island, live status bar,
// home indicator. Drawn at 390×844 and scaled with a GPU transform, so it stays crisp and cheap.
export const DEVICE_W = 390
export const DEVICE_H = 844
const BEZEL = 11
const STATUS_H = 50

function useClock() {
  const fmt = () => new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  const [t, setT] = useState(fmt)
  useEffect(() => { const id = setInterval(() => setT(fmt()), 15_000); return () => clearInterval(id) }, [])
  return t
}

function StatusBar() {
  const time = useClock()
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-50 flex items-center justify-between px-[30px] text-slate-900"
      style={{ height: STATUS_H }}>
      <span className="w-[66px] text-center text-[16px] font-semibold tracking-tight">{time}</span>
      <span className="flex items-center gap-[6px]">
        <svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor" aria-hidden>
          <rect x="0" y="8" width="3" height="4" rx="1" /><rect x="5" y="5.5" width="3" height="6.5" rx="1" />
          <rect x="10" y="3" width="3" height="9" rx="1" /><rect x="15" y="0" width="3" height="12" rx="1" />
        </svg>
        <svg width="16" height="12" viewBox="0 0 16 12" fill="currentColor" aria-hidden>
          <path d="M8 2.2c2.3 0 4.4.9 6 2.4l1.2-1.2A10.2 10.2 0 0 0 8 .5 10.2 10.2 0 0 0 .8 3.4L2 4.6a8.5 8.5 0 0 1 6-2.4Zm0 3.4c1.4 0 2.6.5 3.6 1.4l1.2-1.2A6.8 6.8 0 0 0 8 3.9a6.8 6.8 0 0 0-4.8 1.9L4.4 7c1-.9 2.2-1.4 3.6-1.4Zm0 3.4c-.5 0-1 .2-1.3.5L8 11l1.3-1.5A1.9 1.9 0 0 0 8 9Z" />
        </svg>
        <span className="relative flex h-[13px] w-[27px] items-center rounded-[4px] border border-slate-900/40 p-[1.5px]">
          <span className="h-full w-[78%] rounded-[2px] bg-slate-900" />
          <span className="absolute -right-[3px] top-1/2 h-[4px] w-[1.5px] -translate-y-1/2 rounded-r bg-slate-900/40" />
        </span>
      </span>
    </div>
  )
}

export function Device({ children, scale = 1 }: { children: ReactNode; scale?: number }) {
  return (
    <div style={{ width: DEVICE_W * scale, height: DEVICE_H * scale }} className="relative shrink-0">
      <div className="absolute left-0 top-0 origin-top-left" style={{ width: DEVICE_W, height: DEVICE_H, transform: `scale(${scale})` }}>
        {/* side buttons */}
        <span className="absolute -left-[3px] top-[116px] h-[30px] w-[4px] rounded-l bg-[#3a3a3c]" />
        <span className="absolute -left-[3px] top-[170px] h-[56px] w-[4px] rounded-l bg-[#3a3a3c]" />
        <span className="absolute -left-[3px] top-[236px] h-[56px] w-[4px] rounded-l bg-[#3a3a3c]" />
        <span className="absolute -right-[3px] top-[196px] h-[86px] w-[4px] rounded-r bg-[#3a3a3c]" />
        {/* titanium frame */}
        <div className="absolute inset-0 rounded-[62px] p-[3px] shadow-[0_40px_80px_-20px_rgba(0,0,0,.75),0_0_0_1px_rgba(255,255,255,.06)]"
          style={{ background: 'linear-gradient(145deg,#5b5d61 0%,#2b2c2f 35%,#1c1d20 60%,#4a4c50 100%)' }}>
          <div className="h-full w-full rounded-[59px] bg-black" style={{ padding: BEZEL - 3 }}>
            <div className="relative h-full w-full overflow-hidden rounded-[51px] bg-slate-50" style={{ isolation: 'isolate' }}>
              <StatusBar />
              <div className="absolute left-1/2 top-[11px] z-50 h-[35px] w-[122px] -translate-x-1/2 rounded-full bg-black" />
              <div className="absolute inset-x-0 bottom-0" style={{ top: STATUS_H }}>{children}</div>
              <div className="pointer-events-none absolute bottom-[8px] left-1/2 z-50 h-[5px] w-[134px] -translate-x-1/2 rounded-full bg-slate-900/80" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
