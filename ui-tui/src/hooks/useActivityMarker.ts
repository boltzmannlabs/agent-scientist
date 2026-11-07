import { useTabStatus } from '@sci/ink'
import { useEffect, useState } from 'react'

const FRAMES = ['●··', '·●·', '··●', '·●·']

/** Animate only during work; waiting and idle titles remain still. */
export function useActivityMarker(busy: boolean, waiting: boolean): string {
  const nativeProgress = process.env.TERM_PROGRAM === 'vscode'
  const [frame, setFrame] = useState(0)
  useTabStatus(waiting ? 'waiting' : busy ? 'busy' : 'idle')

  useEffect(() => {
    if (!busy || waiting || nativeProgress) {return}
    const timer = setInterval(() => setFrame(value => (value + 1) % FRAMES.length), 600)

    return () => clearInterval(timer)
  }, [busy, waiting, nativeProgress])

  return nativeProgress ? '' : waiting ? '?' : busy ? FRAMES[frame]! : '·'
}
