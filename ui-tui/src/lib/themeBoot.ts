/** Flash-free boot cache for the fixed dark TUI palette and its branding. */

import { readFileSync, renameSync, writeFileSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

import type { Theme } from '../theme.js'

interface BootThemeFile {
  theme?: Theme
  version: 1
}

// Profile-aware: the Python launcher exports SCI_HOME before spawning the TUI.
const bootFilePath = () => join(process.env.SCI_HOME ?? join(homedir(), '.sci'), 'tui-theme-boot.json')

// Never touch the user's real ~/.sci from test runs (the TS suite has no SCI_HOME isolation fixture).
const isTestRun = () => !!process.env.VITEST || process.env.NODE_ENV === 'test'

const looksLikeTheme = (value: unknown): value is Theme => {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const theme = value as Partial<Theme>

  return (
    typeof theme.color === 'object' &&
    theme.color !== null &&
    typeof theme.color.text === 'string' &&
    typeof theme.color.primary === 'string' &&
    typeof theme.brand === 'object' &&
    theme.brand !== null &&
    typeof theme.brand.name === 'string'
  )
}

export const isDarkTheme = (theme: Theme): boolean => {
  const canvas = theme.surfaces?.canvas ?? theme.color.completionBg
  const match = /^#([0-9a-f]{6})$/i.exec(canvas)

  if (!match) {
    return false
  }

  const hex = match[1]!
  const rgb = [0, 2, 4].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
  const linear = rgb.map(value => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))
  const luminance = 0.2126 * linear[0]! + 0.7152 * linear[1]! + 0.0722 * linear[2]!

  return luminance < 0.5
}

export interface BootTheme {
  theme: Theme
}

/** Read the cached boot theme. Null on first launch / damage / test runs. */
export function readBootTheme(): BootTheme | null {
  if (isTestRun()) {
    return null
  }

  try {
    const raw = JSON.parse(readFileSync(bootFilePath(), 'utf8')) as BootThemeFile

    return raw.version === 1 && looksLikeTheme(raw.theme) && isDarkTheme(raw.theme) ? { theme: raw.theme } : null
  } catch {
    return null
  }
}

let writeTimer: NodeJS.Timeout | null = null

/** Persist the resolved theme (debounced, atomic, fire-and-forget). */
export function writeBootTheme(theme: Theme): void {
  if (isTestRun()) {
    return
  }

  if (writeTimer) {
    clearTimeout(writeTimer)
  }

  writeTimer = setTimeout(() => {
    writeTimer = null

    try {
      const payload: BootThemeFile = { theme, version: 1 }
      const path = bootFilePath()
      const tmp = `${path}.tmp`

      writeFileSync(tmp, JSON.stringify(payload))
      renameSync(tmp, path)
    } catch {
      // Cache write failures are cosmetic — next launch uses the fixed palette.
    }
  }, 400)

  writeTimer.unref?.()
}

export const bootTheme: Theme | null = readBootTheme()?.theme ?? null
