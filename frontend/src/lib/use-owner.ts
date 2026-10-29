import { useOutletContext } from 'react-router-dom'
import type { Identity } from './owner-api'
export function useOwner() {
  return useOutletContext<Identity & { specialist: NonNullable<Identity['specialist']> }>()
}
