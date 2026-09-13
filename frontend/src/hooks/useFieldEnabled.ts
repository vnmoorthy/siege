import { useCallback, useState } from 'react'

const FIELD_KEY = 'siege_field'

/** War-room battlefield (SiegeField) on/off, persisted in localStorage. Default on. */
export function useFieldEnabled(): [boolean, () => void] {
  const [on, setOn] = useState<boolean>(() => {
    try {
      return localStorage.getItem(FIELD_KEY) !== '0'
    } catch {
      return true
    }
  })
  const toggle = useCallback(() => {
    setOn((v) => {
      const next = !v
      try {
        localStorage.setItem(FIELD_KEY, next ? '1' : '0')
      } catch {
        // storage unavailable
      }
      return next
    })
  }, [])
  return [on, toggle]
}
