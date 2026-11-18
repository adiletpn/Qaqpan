import { useEffect, useState } from 'react'
import { api, type Stage } from '../api'

export const STEPS = [
  { id: 'written', n: 1, title: 'Написали', layer: 'Проверка сообщений' },
  { id: 'called', n: 2, title: 'Позвонили', layer: '«Банк мне звонит?»' },
  { id: 'persuaded', n: 3, title: 'Уговорили перевести', layer: 'Умный перевод + семья' },
  { id: 'received', n: 4, title: 'Получили деньги', layer: 'Сеть защиты' },
]

export function useStage(ms = 900) {
  const [stage, setStage] = useState<Stage | null>(null)
  const [offline, setOffline] = useState(false)
  useEffect(() => {
    let alive = true
    const run = () => api.stage()
      .then(d => { if (alive) { setStage(d); setOffline(false) } })
      .catch(() => { if (alive) setOffline(true) })
    run()
    const t = setInterval(run, ms)
    return () => { alive = false; clearInterval(t) }
  }, [ms])
  return { stage, offline }
}

// Order = the demo script (docs/DEMO_SCENARIO.md)
export const ACTIONS = [
  { key: '1', action: 'sms', title: 'SMS «ЭЦП истекает» → Айгерим', hint: 'Она нажимает на уведомление и проверяет его' },
  { key: '2', action: 'call', title: 'Звонок «службы безопасности» → Айгерим', hint: 'Ответить → «Банк мне звонит?»' },
  { key: '3', action: 'transfer_aigerim', title: 'Мошенник диктует перевод 900 000 ₸', hint: 'Аудару → «Жоқ» ×3 (подсказали) → у Ержана push → открыть → «Отклонить перевод»' },
  { key: '4', action: 'transfer_madina', title: 'Мадина платит 150 000 ₸ на тот же счёт', hint: 'После жалобы Айгерим → предупреждение' },
  { key: '5', action: 'victim', title: 'Экран «Если вас обманули»', hint: 'Финал: готовое заявление' },
  { key: 'B', action: 'bank_calls_madina', title: 'Настоящий звонок банка → Мадина', hint: 'Для вопросов: «а если звонит правда банк?»' },
  { key: 'E', action: 'end_call', title: 'Завершить звонок Айгерим', hint: '' },
  { key: 'R', action: 'reset', title: 'Сброс демо', hint: 'Перед каждым прогоном' },
]

export function useDirectorHotkeys(onError?: (msg: string) => void) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') || e.metaKey || e.ctrlKey || e.altKey) return
      const a = ACTIONS.find(x => x.key.toLowerCase() === e.key.toLowerCase())
      if (a) {
        e.preventDefault()
        api.director(a.action).catch(err => onError?.(err instanceof Error ? err.message : 'Ошибка'))
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onError])
}
