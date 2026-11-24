import { useStore } from '@nanostores/react'
import { Box, Text, useStdout } from '@sci/ink'
import { useEffect, useState } from 'react'

import { useOptionalGateway } from '../app/gatewayContext.js'
import { $uiState } from '../app/uiStore.js'
import { t } from '../i18n/runtime.js'

import { type PetGrid, PetKitty, PetSprite } from './petSprite.js'

export interface ImagePreviewResult {
  ok: boolean
  graphics?: string
  grid?: PetGrid
  imageId?: number
  color?: string
  placeholder?: string[]
  transmit?: string
}

export const supportsInlineGraphics = (env: NodeJS.ProcessEnv, tty: boolean) =>
  tty &&
  env.SCI_TUI_DASHBOARD !== '1' &&
  env.TERM_PROGRAM !== 'vscode' &&
  env.TERM_PROGRAM !== 'WezTerm' &&
  !env.WEZTERM_PANE &&
  (Boolean(env.KITTY_WINDOW_ID) || /kitty|ghostty/i.test(env.TERM ?? '') || env.TERM_PROGRAM === 'ghostty')

export const isPreviewImage = (path: string) =>
  /^(?:\/|[a-z]:[\\/])/i.test(path) && /\.(?:png|jpe?g|webp|gif|bmp)$/i.test(path)

export function ImagePreview({ path, cols }: { path: string; cols: number }) {
  const gateway = useOptionalGateway()
  const { sid, busy } = useStore($uiState)
  const { write } = useStdout()
  const [preview, setPreview] = useState<ImagePreviewResult | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const width = Math.max(4, Math.min(160, cols))

  useEffect(() => {
    if (!gateway || !sid || busy) {
      return
    }

    setPreview(null)
    setUnavailable(false)
    let cancelled = false
    gateway.gw
      .request<ImagePreviewResult>('image.preview', {
        session_id: sid,
        path,
        cols: width,
        graphics: supportsInlineGraphics(process.env, Boolean(process.stdout.isTTY))
      })
      .then(result => {
        if (cancelled) {
          return
        }

        if (result?.ok) {
          setPreview(result)
        } else {
          setUnavailable(true)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUnavailable(true)
        }
      })

    return () => {
      cancelled = true
    }
  }, [gateway, sid, busy, path, width])

  useEffect(() => {
    if (!preview?.transmit || !preview.imageId) {
      return
    }

    write(preview.transmit)

    return () => {
      write(`\x1b_Ga=d,d=i,i=${preview.imageId},q=2\x1b\\`)
    }
  }, [preview, write])

  if (unavailable) {
    return <Text dimColor>{t('chatBits.imagePreview.unavailable')}</Text>
  }

  if (!preview?.ok) {
    return null
  }

  return (
    <Box flexDirection="column">
      {preview.graphics === 'kitty' && preview.color && preview.placeholder ? (
        <PetKitty color={preview.color} placeholder={preview.placeholder} />
      ) : preview.grid ? (
        <PetSprite grid={preview.grid} />
      ) : null}
      <Text dimColor>{t('chatBits.imagePreview.detail')}</Text>
    </Box>
  )
}
