import type { ReactNode } from 'react'

type LtrTextProps = {
  children: ReactNode
}

/** Isolate LTR runs (ids, codes, English) inside RTL UI. */
export function LtrText({ children }: LtrTextProps) {
  return <bdi dir="ltr">{children}</bdi>
}
