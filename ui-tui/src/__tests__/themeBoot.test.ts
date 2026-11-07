import { describe, expect, it } from 'vitest'

import { isDarkTheme } from '../lib/themeBoot.js'
import { DARK_THEME } from '../theme.js'

describe('dark-only TUI boot cache', () => {
  it('accepts the dark built-in theme', () => {
    expect(isDarkTheme(DARK_THEME)).toBe(true)
  })

  it('rejects cached themes with a light canvas', () => {
    const light = {
      ...DARK_THEME,
      surfaces: { ...DARK_THEME.surfaces, canvas: '#ffffff' }
    }

    expect(isDarkTheme(light)).toBe(false)
  })
})
