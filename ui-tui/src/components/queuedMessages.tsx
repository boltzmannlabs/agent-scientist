import { Box, Text } from '@sci/ink'

import { useT } from '../i18n/useT.js'
import { compactPreview } from '../lib/text.js'
import type { Theme } from '../theme.js'

export const QUEUE_WINDOW = 3

export function getQueueWindow(queueLen: number, queueEditIdx: number | null) {
  const start =
    queueEditIdx === null ? 0 : Math.max(0, Math.min(queueEditIdx - 1, Math.max(0, queueLen - QUEUE_WINDOW)))

  const end = Math.min(queueLen, start + QUEUE_WINDOW)

  return { end, showLead: start > 0, showTail: end < queueLen, start }
}

export function QueuedMessages({ cols, queueEditIdx, queued, t }: QueuedMessagesProps) {
  const T = useT().chatBits.queued

  if (!queued.length) {
    return null
  }

  const q = getQueueWindow(queued.length, queueEditIdx)

  return (
    <Box backgroundColor={t.surfaces?.elevated} flexDirection="column" marginTop={1} paddingX={1}>
      <Text bold color={t.color.label}>
        {`${T.header(queued.length)}${queueEditIdx !== null ? T.editing(queueEditIdx + 1) : ''}`}
      </Text>

      {q.showLead && <Text color={t.color.muted}> …</Text>}

      {queued.slice(q.start, q.end).map((item, i) => {
        const idx = q.start + i
        const active = queueEditIdx === idx

        return (
          <Text color={active ? t.color.accent : t.color.text} key={`${idx}-${item.slice(0, 16)}`}>
            {active ? '▸' : ' '} {compactPreview(item, Math.max(16, cols - 10))}
          </Text>
        )
      })}

      {q.showTail && (
        <Text color={t.color.muted}>
          {'  '}
          {T.more(queued.length - q.end)}
        </Text>
      )}
    </Box>
  )
}

interface QueuedMessagesProps {
  cols: number
  queueEditIdx: number | null
  queued: string[]
  t: Theme
}
