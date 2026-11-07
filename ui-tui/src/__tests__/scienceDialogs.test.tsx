import { PassThrough } from 'node:stream'

import { Box, renderSync, Text } from '@sci/ink'
import { stripAnsi } from '@sci/shared/ansi'
import React from 'react'
import { expect, it, vi } from 'vitest'

import { BoltzmannLogo } from '../components/boltzmannLogo.js'
import { SecretPrompt } from '../components/maskedPrompt.js'
import { ModelPicker } from '../components/modelPicker.js'
import { ApprovalPrompt, ClarifyPrompt } from '../components/prompts.js'
import type { GatewayClient } from '../gatewayClient.js'
import { useActivityMarker } from '../hooks/useActivityMarker.js'
import { DARK_THEME, LIGHT_THEME } from '../theme.js'

it('animates the welcome logo and stops repainting after interaction or unmount', async () => {
  vi.useFakeTimers()
  const view = mount(<BoltzmannLogo animate t={DARK_THEME} />, 40)

  try {
    await vi.advanceTimersByTimeAsync(100)
    const initial = view.raw()
    await vi.advanceTimersByTimeAsync(2600)
    expect(view.raw()).not.toBe(initial)
    expect(view.text()).toContain('BOLTZMANN LABS')
    view.rerender(<BoltzmannLogo animate={false} t={DARK_THEME} />)
    await vi.advanceTimersByTimeAsync(100)
    const stopped = view.raw()
    await vi.advanceTimersByTimeAsync(2000)
    expect(view.raw()).toBe(stopped)
  } finally {
    view.close()
    vi.useRealTimers()
  }
})

function mount(element: React.ReactNode, cols: number, rows = 40) {
  const stdout = Object.assign(new PassThrough(), { columns: cols, isTTY: false, rows })
  const stdin = Object.assign(new PassThrough(), { isTTY: true, setRawMode: vi.fn(), ref: vi.fn(), unref: vi.fn() })
  let output = ''
  stdout.on('data', chunk => {
    output += chunk.toString()
  })

  const view = renderSync(<Box width={cols}>{element}</Box>, {
    stdout: stdout as NodeJS.WriteStream,
    stdin: stdin as unknown as NodeJS.ReadStream,
    stderr: new PassThrough() as NodeJS.WriteStream,
    patchConsole: false
  })

  return {
    stdin,
    text: () => stripAnsi(output),
    raw: () => output,
    rerender: (element: React.ReactNode) => view.rerender(<Box width={cols}>{element}</Box>),
    close: () => {
      view.unmount()
      view.cleanup()
    }
  }
}

it.each([32, 110])('keeps the login secret masked while submitting the exact input at %i columns', async cols => {
  for (const t of [DARK_THEME, LIGHT_THEME]) {
    const submit = vi.fn()

    const view = mount(
      <SecretPrompt cols={cols} envVar="BOLTZMANN_API_KEY" onSubmit={submit} prompt="API key (hidden)" t={t} />,
      cols
    )

    try {
      await vi.waitFor(() => expect(view.text()).toContain('Boltzmann login'))
      view.stdin.write('fixture-only-key')
      await vi.waitFor(() => expect(view.text()).toContain('••••'))
      expect(view.text()).not.toContain('fixture-only-key')
      view.stdin.write('\r')
      await vi.waitFor(() => expect(submit).toHaveBeenCalledWith('fixture-only-key'))
      expect(view.text()).not.toContain('fixture-only-key')
    } finally {
      view.close()
    }
  }
})

it.each([32, 100])('selects the exact filtered model without mutating the catalog at %i columns', async cols => {
  const catalog = {
    model: 'qwen',
    providers: [
      {
        name: 'boltzmann_models',
        slug: 'boltzmann_models',
        authenticated: true,
        is_current: true,
        models: ['qwen', 'discoveryrsi', 'glm', 'codex'],
        capabilities: { glm: { reasoning: false } }
      }
    ]
  }

  const before = JSON.stringify(catalog)

  for (const t of [DARK_THEME, LIGHT_THEME]) {
    const select = vi.fn()
    const request = vi.fn().mockResolvedValue(catalog)

    const view = mount(
      <ModelPicker
        gw={{ request } as unknown as GatewayClient}
        maxWidth={cols}
        onCancel={vi.fn()}
        onSelect={select}
        sessionId="profile-a"
        t={t}
      />,
      cols,
      24
    )

    try {
      await vi.waitFor(() => expect(view.text()).toContain('boltzmann_models'))
      view.stdin.write('\r')
      await vi.waitFor(() => expect(view.text()).toContain('discoveryrsi'))
      let filter = ''

      for (const character of 'glm') {
        filter += character
        view.stdin.write(character)
        await vi.waitFor(() => expect(view.text()).toContain(`${filter}▎`))
      }

      await vi.waitFor(() => expect(view.text()).toContain('glm▎'))
      view.stdin.write('\r')
      await vi.waitFor(() =>
        expect(select).toHaveBeenCalledWith(expect.stringMatching(/^glm --provider boltzmann_models /))
      )
      expect(JSON.stringify(catalog)).toBe(before)
      expect(request).toHaveBeenCalledExactlyOnceWith('model.options', {
        session_id: 'profile-a',
        include_unconfigured: true
      })
    } finally {
      view.close()
    }
  }
})

it('keeps approval cancellation and profile selection intact in the surfaced dialogs', async () => {
  const choose = vi.fn()

  const approval = mount(
    <ApprovalPrompt
      cols={80}
      onChoice={choose}
      req={{ requestId: 'fixture', command: 'printf fixture', description: 'Review command' }}
      t={DARK_THEME}
    />,
    80
  )

  try {
    await vi.waitFor(() => expect(approval.text()).toContain('printf fixture'))
    approval.stdin.write('\x1b')
    await vi.waitFor(() => expect(choose).toHaveBeenCalledWith('deny'))
  } finally {
    approval.close()
  }

  const answer = vi.fn()

  const req = {
    requestId: 'fixture',
    questions: [{ qid: 'profile', question: 'Choose a profile', choices: ['main', 'omics', 'Cancel'] }]
  }

  const before = JSON.stringify(req)

  const picker = mount(
    <ClarifyPrompt cols={80} onCancel={vi.fn()} onQuestionAnswer={answer} req={req} t={DARK_THEME} />,
    80
  )

  try {
    await vi.waitFor(() => expect(picker.text()).toContain('Choose a profile'))
    expect(picker.text()).not.toMatch(/(?:1\. main|2\. omics|3\. Cancel)/)
    picker.stdin.write('\x1b[B')
    await vi.waitFor(() => expect(picker.text()).toContain('● omics'))
    picker.stdin.write('\r')
    await vi.waitFor(() => expect(answer).toHaveBeenCalledWith('profile', 'omics'))
    expect(JSON.stringify(req)).toBe(before)
  } finally {
    picker.close()
  }
})

it('animates the work marker while keeping idle and waiting markers stable', async () => {
  vi.stubEnv('TERM_PROGRAM', 'xterm')

  function Markers() {
    const busy = useActivityMarker(true, false)
    const idle = useActivityMarker(false, false)
    const waiting = useActivityMarker(true, true)

    return <Text>{`busy=${busy} idle=${idle} waiting=${waiting}`}</Text>
  }

  const view = mount(<Markers />, 80)

  try {
    await vi.waitFor(() => expect(view.text()).toContain('busy=●·· idle=· waiting=?'))
    await vi.waitFor(() => expect(view.text()).toContain('busy=·●· idle=· waiting=?'), { timeout: 3000 })
  } finally {
    view.close()
    vi.unstubAllEnvs()
  }
})

it('reports VS Code native progress through the renderer and clears waiting, idle and unmount', async () => {
  vi.stubEnv('TERM_PROGRAM', 'vscode')
  vi.stubEnv('TMUX', '')
  vi.stubEnv('STY', '')
  const descriptor = Object.getOwnPropertyDescriptor(process.stdout, 'isTTY')
  Object.defineProperty(process.stdout, 'isTTY', { configurable: true, value: true })

  function Status({ busy, waiting = false }: { busy: boolean; waiting?: boolean }) {
    return <Text>{`marker=${useActivityMarker(busy, waiting)}`}</Text>
  }

  const start = '\x1b]9;4;3;\x07'
  const stop = '\x1b]9;4;0;\x07'
  const view = mount(<Status busy />, 80)

  try {
    await vi.waitFor(() => expect(view.raw()).toContain(start))
    let offset = view.raw().length
    view.rerender(<Status busy waiting />)
    await vi.waitFor(() => expect(view.raw().slice(offset)).toContain(stop))
    offset = view.raw().length
    view.rerender(<Status busy />)
    await vi.waitFor(() => expect(view.raw().slice(offset)).toContain(start))
    offset = view.raw().length
    view.rerender(<Status busy={false} />)
    await vi.waitFor(() => expect(view.raw().slice(offset)).toContain(stop))
    offset = view.raw().length
    view.rerender(<Status busy />)
    await vi.waitFor(() => expect(view.raw().slice(offset)).toContain(start))
  } finally {
    view.close()

    if (descriptor) {Object.defineProperty(process.stdout, 'isTTY', descriptor)}
    else {delete process.stdout.isTTY}

    vi.unstubAllEnvs()
  }

  expect(view.raw().lastIndexOf(stop)).toBeGreaterThan(view.raw().lastIndexOf(start))
})
