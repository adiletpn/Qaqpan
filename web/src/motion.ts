import type { Transition } from 'framer-motion'

// iOS-like timing: quick start, soft landing
export const EASE: [number, number, number, number] = [0.22, 0.8, 0.2, 1]
export const SPRING: Transition = { type: 'spring', stiffness: 420, damping: 38, mass: 0.9 }

// screen depth decides the direction of the transition: deeper = slides in from the right
export const DEPTH: Record<string, number> = { home: 0, check: 1, transfer: 1, schemes: 1, family: 1, assistant: 1, result: 2, victim: 3 }

export const pageVariants = {
  enter: (dir: number) => ({ x: dir > 0 ? '100%' : '-28%', opacity: dir > 0 ? 1 : 0.6, zIndex: dir > 0 ? 2 : 1 }),
  center: { x: 0, opacity: 1, zIndex: 2, transition: { duration: 0.34, ease: EASE } },
  exit: (dir: number) => ({ x: dir > 0 ? '-28%' : '100%', opacity: dir > 0 ? 0.6 : 1, zIndex: dir > 0 ? 1 : 3, transition: { duration: 0.34, ease: EASE } }),
}

/** Light haptic feedback where the platform supports it (Android Chrome); silently ignored elsewhere. */
export function buzz(pattern: number | number[]) {
  try { navigator.vibrate?.(pattern) } catch { /* not supported */ }
}

export const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
