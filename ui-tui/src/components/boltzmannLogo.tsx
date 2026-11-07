import { Box, Text } from '@sci/ink'
import { useEffect, useRef, useState } from 'react'

import animation from '../../../sci_cli/data/boltzmann-spin.json' with { type: 'json' }
import type { Theme } from '../theme.js'

interface BoltzmannLogoProps {
  animate: boolean
  t: Theme
}

export function BoltzmannLogo({ animate, t }: BoltzmannLogoProps) {
  const [frame, setFrame] = useState(0)
  const stopped = useRef(false)

  useEffect(() => {
    if (!animate) {stopped.current = true}

    if (stopped.current) {return}
    const started = performance.now()

    const timer = setInterval(() => {
      setFrame(Math.floor((performance.now() - started) / animation.frame_ms) % animation.frames.length)
    }, animation.frame_ms)

    return () => clearInterval(timer)
  }, [animate])

  const lines = animation.frames[animate && !stopped.current ? frame : 0]!

  return (
    <Box flexDirection="column" flexShrink={0} marginRight={3} width={34}>
      {lines.map((line, i) => (
        <Text color={t.color.primary} key={i}>
          {line}
        </Text>
      ))}
      <Text bold color={t.color.muted}>
        {'       BOLTZMANN LABS'}
      </Text>
    </Box>
  )
}
