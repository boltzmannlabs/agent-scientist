import { readFileSync } from 'node:fs'

import { afterEach, describe, expect, it, vi } from 'vitest'

function releasePalette(section: 'colors' | 'light_colors') {
  const source = readFileSync(new URL('../../../assets/skins/neon-theme.yaml', import.meta.url), 'utf8')
  let current = ''
  const colors: Record<string, string> = {}

  for (const line of source.split('\n')) {
    const heading = /^(colors|light_colors):$/.exec(line)

    if (heading) {
      current = heading[1]!
    }

    const entry = /^ {2}(\w+): ['"](#[0-9A-Fa-f]{6})['"]$/.exec(line)

    if (current === section && entry) {
      colors[entry[1]!] = entry[2]!
    }
  }

  return colors
}

// `theme.js` reads `process.env` at module-load to compute DEFAULT_THEME,
// and `fromSkin` closes over DEFAULT_THEME.  A developer shell with
// SCI_TUI_THEME=light (or SCI_TUI_BACKGROUND set to something
// bright) would flip the base and turn these assertions into a local-
// only failure.  We sterilize the relevant env vars + dynamically
// import the module fresh so EVERY symbol that closes over the env
// (DEFAULT_THEME, DARK_THEME, LIGHT_THEME, fromSkin) is loaded against
// a known-empty environment.
//
// `detectLightMode` takes env as an explicit arg, so it's safe to import
// statically — but we stay consistent and dynamic-import it too.
const RELEVANT_ENV = [
  'SCI_TUI_LIGHT',
  'SCI_TUI_THEME',
  'SCI_TUI_BACKGROUND',
  'COLORFGBG',
  'COLORTERM',
  'TERM_PROGRAM'
] as const

async function importThemeWithEnv(env: Partial<Record<(typeof RELEVANT_ENV)[number], string>> = {}) {
  for (const key of RELEVANT_ENV) {
    vi.stubEnv(key, env[key] ?? '')
  }

  vi.resetModules()

  return import('../theme.js')
}

async function importThemeWithCleanEnv() {
  return importThemeWithEnv()
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('non-selectable LIGHT_THEME data', () => {
  it('keeps the same shape as DARK_THEME', async () => {
    const { DARK_THEME, LIGHT_THEME } = await importThemeWithCleanEnv()

    expect(Object.keys(LIGHT_THEME.color).sort()).toEqual(Object.keys(DARK_THEME.color).sort())
    expect(LIGHT_THEME.brand).toEqual(DARK_THEME.brand)
  })
})

describe('dark-only TUI palette', () => {
  it('always defaults to DARK_THEME regardless of host appearance signals', async () => {
    const { DEFAULT_THEME, DARK_THEME } = await importThemeWithEnv({
      SCI_TUI_LIGHT: '1',
      SCI_TUI_THEME: 'light',
      SCI_TUI_BACKGROUND: '#ffffff',
      COLORFGBG: '0;15',
      TERM_PROGRAM: 'Apple_Terminal'
    })

    expect(DEFAULT_THEME).toBe(DARK_THEME)
  })

  it('keeps the packaged release palette as the dark base', async () => {
    const { DARK_SEEDS } = await importThemeWithCleanEnv()
    const palette = releasePalette('colors')

    expect(DARK_SEEDS.primary).toBe(palette.banner_title)
    expect(DARK_SEEDS.text).toBe(palette.banner_text)
    expect(DARK_SEEDS.accent).toBe(palette.banner_accent)
  })

  it('ignores light environment signals in the mode resolver', async () => {
    const { detectLightMode, defaultThemeForCurrentBackground } = await importThemeWithCleanEnv()

    expect(detectLightMode({ SCI_TUI_THEME: 'light', SCI_TUI_BACKGROUND: '#ffffff' })).toBe(false)
    expect(defaultThemeForCurrentBackground({ SCI_TUI_LIGHT: '1' })).toBe((await import('../theme.js')).DARK_THEME)
  })
})

describe('fromSkin', () => {
  // `fromSkin` closes over DEFAULT_THEME (which is env-derived), so we
  // must dynamic-import it after sterilizing env — otherwise an ambient
  // SCI_TUI_THEME=light would flip the base palette and make these
  // assertions order-dependent on the developer's shell.

  it('overrides banner colors', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    expect(fromSkin({ banner_title: '#FF0000' }, {}).color.primary).toBe('#FF0000')
  })

  it('preserves unset colors', async () => {
    const { DEFAULT_THEME, fromSkin } = await importThemeWithCleanEnv()

    expect(fromSkin({ banner_title: '#FF0000' }, {}).color.accent).toBe(DEFAULT_THEME.color.accent)
  })

  it('keeps completion surfaces dark even when a skin provides a white fill', async () => {
    const { fromSkin } = await importThemeWithEnv({ SCI_TUI_BACKGROUND: '#ffffff', SCI_TUI_THEME: 'light' })
    const theme = fromSkin(
      { banner_accent: '#000000', background: '#ffffff', terminal_elevated: '#ffffff', completion_menu_bg: '#ffffff' },
      {}
    )

    expect(luminance(theme.color.completionBg)).toBeLessThanOrEqual(0.35)
    expect(luminance(theme.surfaces!.canvas)).toBeLessThanOrEqual(0.35)
    expect(luminance(theme.surfaces!.elevated)).toBeLessThanOrEqual(0.35)
  })

  it('rejects wrong-polarity fills even when skin-authored (terminal owns the canvas)', async () => {
    // Dark terminal + white menu fill: unlike the desktop app, the TUI cannot
    // paint its own canvas, so cross-polarity fills fall back to the derived
    // ladder values, which are mixed from the real background and therefore
    // polarity-correct by construction.
    const { fromSkin } = await importThemeWithCleanEnv()

    const theme = fromSkin({ banner_accent: '#000000', completion_menu_bg: '#ffffff' }, {})

    expect(luminance(theme.color.completionBg)).toBeLessThanOrEqual(0.35)
    expect(luminance(theme.color.completionCurrentBg)).toBeLessThanOrEqual(0.35)
  })

  it('uses active completion color as the selection highlight fallback', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    const theme = fromSkin({ completion_menu_current_bg: '#123456' }, {})

    expect(theme.color.selectionBg).toBe('#123456')
  })

  it('maps completion meta background colors from skins', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    const theme = fromSkin(
      {
        completion_menu_meta_bg: '#111111',
        completion_menu_meta_current_bg: '#222222'
      },
      {}
    )

    expect(theme.color.completionMetaBg).toBe('#111111')
    expect(theme.color.completionMetaCurrentBg).toBe('#222222')
  })

  it('lets selection_bg override completion highlight colors', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    const theme = fromSkin({ completion_menu_current_bg: '#123456', selection_bg: '#654321' }, {})

    expect(theme.color.selectionBg).toBe('#654321')
  })

  it('overrides branding', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()
    const { brand } = fromSkin({}, { agent_name: 'TestBot', prompt_symbol: '$' })

    expect(brand.name).toBe('TestBot')
    expect(brand.prompt).toBe('$')
  })

  it('normalizes skin prompt symbols to trimmed single-line text', async () => {
    const { DEFAULT_THEME, fromSkin } = await importThemeWithCleanEnv()

    expect(fromSkin({}, { prompt_symbol: ' ⚔ ❯ \n' }).brand.prompt).toBe('⚔ ❯')
    expect(fromSkin({}, { prompt_symbol: ' Ψ > \n' }).brand.prompt).toBe('Ψ >')
    expect(fromSkin({}, { prompt_symbol: '\n\t' }).brand.prompt).toBe(DEFAULT_THEME.brand.prompt)
  })

  // ── A skin that authors a background OWNS its polarity ──────────────
  // The TUI paints the terminal with the skin's background (OSC-11), so
  // every adaptation pass must run against the skin's canvas, not the host
  // profile the skin just covered. The real-world failure: a pure-black
  // skin on light-mode Apple Terminal got its text ansi256-bucketed for a
  // light background that no longer exists — invisible on the painted black.

  it('a dark-background skin on light Apple Terminal keeps its truecolor text (no light-mode bucketing)', async () => {
    const { fromSkin } = await importThemeWithEnv({ TERM_PROGRAM: 'Apple_Terminal' })

    const theme = fromSkin({ background: '#000000', ui_accent: '#ff9e18', ui_text: '#ffa726' }, {})

    expect(theme.color.text).toBe('#ffa726')
    expect(theme.color.prompt).not.toMatch(/^ansi256/)
  })

  it('a skin background outranks the cached host background for adaptation and tone derivation', async () => {
    const { fromSkin } = await importThemeWithEnv({ SCI_TUI_BACKGROUND: '#ffffff' })

    const theme = fromSkin({ background: '#000000', ui_text: '#ffa726' }, {})

    // Text is not contrast-lifted toward a white host it painted over…
    expect(theme.color.text).toBe('#ffa726')
    // …and derived fills mix against the skin's black, not the host's white.
    expect(luminance(theme.color.completionBg)).toBeLessThanOrEqual(0.35)
    expect(luminance(theme.color.statusBg)).toBeLessThanOrEqual(0.35)
  })

  it('never treats a light skin or terminal hint as a light-mode switch', async () => {
    const { skinIsLight, fromSkin } = await importThemeWithEnv({ SCI_TUI_THEME: 'light' })

    expect(skinIsLight({ background: '#ffffff' })).toBe(false)
    expect(fromSkin({ background: '#000000', ui_text: '#ffa726' }, {}).color.text).toBe('#ffa726')
  })

  it('maps ui_ color keys + cascades to status', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()
    const { color } = fromSkin({ ui_ok: '#008000' }, {})

    // The exact value may be contrast-lifted against the background; the
    // contract is the cascade (ok drives statusGood) and the hue surviving.
    expect(color.statusGood).toBe(color.ok)
    expect(color.ok).toMatch(/^#[0-9a-f]{6}$/i)
    expect(luminance(color.ok)).toBeGreaterThan(0)
  })
})

// Rec. 709-ish relative luminance, local to the test so assertions are
// independent of the implementation under test.
const luminance = (hex: string): number => {
  const n = parseInt(hex.replace('#', ''), 16)

  const channel = (v: number) => {
    const c = v / 255

    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }

  return 0.2126 * channel((n >> 16) & 0xff) + 0.7152 * channel((n >> 8) & 0xff) + 0.0722 * channel(n & 0xff)
}

// The bundled slate skin's actual color block — dark-authored (pale pastels,
// no completion/selection backgrounds defined).
const SLATE_COLORS = {
  banner_accent: '#8EA8FF',
  banner_border: '#4169e1',
  banner_dim: '#4b5563',
  banner_text: '#c9d1d9',
  banner_title: '#7eb8f6',
  prompt: '#c9d1d9',
  session_border: '#4b5563',
  session_label: '#7eb8f6',
  ui_accent: '#7eb8f6',
  ui_error: '#F7A072',
  ui_label: '#8EA8FF',
  ui_ok: '#63D0A6',
  ui_warn: '#e6a855'
}

describe('derived tone ladder', () => {
  it('preserves explicit identity and fill seeds while deriving readable secondary tones', async () => {
    const { DARK_SEEDS, DARK_THEME, LIGHT_SEEDS, LIGHT_THEME, contrastRatio } = await importThemeWithCleanEnv()

    for (const [seeds, theme] of [
      [DARK_SEEDS, DARK_THEME],
      [LIGHT_SEEDS, LIGHT_THEME]
    ] as const) {
      expect(theme.color.primary).toBe(seeds.primary)
      expect(theme.color.accent).toBe(seeds.accent)
      expect(theme.color.completionBg).toBe(seeds.surface)
      expect(theme.color.completionCurrentBg).toBe(seeds.activeRow)
      expect(theme.color.selectionBg).toBe(seeds.selection)
      expect(contrastRatio(theme.color.muted, seeds.bg)!).toBeGreaterThanOrEqual(2.8)
      expect(contrastRatio(theme.color.label, seeds.bg)!).toBeGreaterThanOrEqual(3.0)
    }
  })

  it('derives dim/secondary tones from the skin identity, not another palette', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    // A seeds-only skin (no dim/label/menu keys authored at all).
    const { color } = fromSkin({ banner_accent: '#DD4A3A', banner_text: '#F1E6CF', banner_title: '#C7A96B' }, {})

    // Muted recedes from THIS skin's text toward the background with an
    // accent tint — a red-family derivative, never another skin's gold.
    expect(color.muted).not.toBe(color.text)
    expect(luminance(color.muted)).toBeLessThan(luminance(color.text))

    const rgb = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
    const [mr, , mb] = rgb(color.muted)

    expect(mr).toBeGreaterThan(mb!)

    // The active-row chip is the surface tinted with the skin accent —
    // redder than the plain surface.
    const [sr] = rgb(color.completionBg)

    expect(rgb(color.completionCurrentBg)[0]).toBeGreaterThan(sr!)
  })

  it('authored tones still override the ladder', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()
    const { color } = fromSkin({ banner_dim: '#AA8844', banner_text: '#F1E6CF' }, {})

    expect(color.muted).toBe('#AA8844')
    expect(color.sessionLabel).toBe('#AA8844')
  })
})

describe('dark-only skin rendering', () => {
  it('keeps host appearance signals from changing the dark skin palette', async () => {
    const { fromSkin, skinIsLight } = await importThemeWithEnv({
      SCI_TUI_BACKGROUND: '#ffffff',
      SCI_TUI_THEME: 'light',
      SCI_TUI_LIGHT: '1'
    })
    const theme = fromSkin({ background: '#000000', ui_text: '#ffa726' }, {})

    expect(skinIsLight({ background: '#ffffff' }, { SCI_TUI_THEME: 'light' })).toBe(false)
    expect(theme.color.text).toBe('#ffa726')
    expect(luminance(theme.color.completionBg)).toBeLessThanOrEqual(0.35)
  })

  it('gives tool + thinking their own keys, defaulting to accent + muted', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    // Independent override: recoloring tool/thinking doesn't leak into accent.
    // (Values flow through #20379's contrast adaptation, so assert the
    //  independence contract, not raw pre-adaptation hexes.)
    const themed = fromSkin({ ui_accent: '#3aa0ff', ui_tool: '#ff0000', ui_thinking: '#00ff00' }, {})
    const baseline = fromSkin({ ui_accent: '#3aa0ff' }, {})
    expect(themed.color.tool).toBe('#ff0000')
    expect(themed.color.thinking).toBe('#00ff00')
    expect(themed.color.tool).not.toBe(themed.color.accent)
    expect(themed.color.accent).toBe(baseline.color.accent) // override didn't touch accent

    // Default: tool follows accent, thinking follows muted — same source →
    // identical after adaptation.
    const fallback = fromSkin({ ui_accent: '#3aa0ff', banner_dim: '#8a8a8a' }, {})
    expect(fallback.color.tool).toBe(fallback.color.accent)
    expect(fallback.color.thinking).toBe(fallback.color.muted)
  })

  it('gives code syntax its own keys, defaulting to accent/text/border/muted', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    const themed = fromSkin(
      { syntax_string: '#aa0000', syntax_number: '#00aa00', syntax_keyword: '#0000aa', syntax_comment: '#888888' },
      {}
    )

    expect(themed.color.syntaxString).toBe('#aa0000')
    expect(themed.color.syntaxNumber).toBe('#00aa00')
    expect(themed.color.syntaxKeyword).toBe('#0000aa')
    expect(themed.color.syntaxComment).toBe('#888888')

    const fallback = fromSkin({ ui_accent: '#abcdef' }, {})
    expect(fallback.color.syntaxString).toBe('#abcdef') // string follows accent
  })

  it('lets skins override diff colors', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    const { color } = fromSkin(
      { diff_added: '#0a0', diff_removed: '#a00', diff_added_word: '#0f0', diff_removed_word: '#f00' },
      {}
    )

    expect(color.diffAdded).toBe('#0a0')
    expect(color.diffRemoved).toBe('#a00')
    expect(color.diffAddedWord).toBe('#0f0')
    expect(color.diffRemovedWord).toBe('#f00')
  })

  it('maps the status bar from skin status_bar_* keys', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()

    const { color } = fromSkin(
      {
        status_bar_bg: '#101020',
        status_bar_text: '#e0e0e0',
        status_bar_bad: '#ff8800',
        status_bar_critical: '#ff0000'
      },
      {}
    )

    expect(color.statusBg).toBe('#101020')
    expect(color.statusFg).toBe('#e0e0e0')
    expect(color.statusBad).toBe('#ff8800')
    expect(color.statusCritical).toBe('#ff0000')
  })

  it('falls the status bar back to background + semantic colors', async () => {
    const { fromSkin } = await importThemeWithCleanEnv()
    const { color } = fromSkin({ background: '#0a0a0a', banner_text: '#fafafa', ui_error: '#dd2222' }, {})

    // background paints the surface → status/completion bg; banner_text → status
    // fg; ui_error → critical. Semantic hues flow through contrast adaptation,
    // so `statusCritical` is asserted to track `ui_error` identically rather
    // than pinning an adapted hex.
    expect(color.statusBg).toBe('#0a0a0a')
    expect(color.completionBg).toBe('#0a0a0a')
    expect(color.statusFg).toBe('#fafafa')
    expect(color.statusCritical).toBe(fromSkin({ ui_error: '#dd2222' }, {}).color.error)
  })
})

describe('themeToneHex', () => {
  it('resolves a tone to the literal color it paints as', async () => {
    const { themeToneHex } = await importThemeWithCleanEnv()

    // 232+ is the grayscale ramp (8 + (n-232)*10); 16-231 is the 6x6x6 cube.
    expect(themeToneHex('ansi256(238)')).toBe('#444444')
    expect(themeToneHex('ansi256(161)')).toBe('#d7005f')
    // An authored hex is already literal.
    expect(themeToneHex('#e77fa3')).toBe('#e77fa3')
    // No paintable color ⇒ '', which releases the terminal default.
    expect(themeToneHex('')).toBe('')
    expect(themeToneHex('ansi256(999)')).toBe('')
    expect(themeToneHex('inherit')).toBe('')
  })

  it('makes every tone paintable on a quantizing terminal', async () => {
    // The contract OSC-10 depends on: whatever the palette normalizer does to
    // a tone, themeToneHex still yields a literal `#rrggbb`. Asserted over the
    // whole palette so a new tone can't silently regress the default paint.
    const { fromSkin, themeToneHex } = await importThemeWithEnv({ TERM_PROGRAM: 'Apple_Terminal' })
    const { color } = fromSkin({ background: '#f6f9fd', ui_text: '#4a4550' }, {})

    for (const tone of Object.values(color)) {
      expect(themeToneHex(tone)).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })
})
