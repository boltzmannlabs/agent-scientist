import { Box, NoSelect, Text } from '@sci/ink'
import type { ReactNode } from 'react'
import stringWidth from 'string-width'

import art from '../../../sci_cli/data/science-terminal-art.json' with { type: 'json' }
import { DEFAULT_THEME } from '../theme.js'
import type { Theme } from '../theme.js'
import type { SessionInfo } from '../types.js'

import { BoltzmannLogo } from './boltzmannLogo.js'

interface ScienceWelcomeProps {
  info?: SessionInfo
  cols: number
  t: Theme
  animateLogo?: boolean
}

const LOGO_COLORS = ['#F04FCB', '#B45BFF', '#557BFF', '#28C8F5', '#20D6A5']

export function ScienceWelcome({ info, cols, t, animateLogo = false }: ScienceWelcomeProps) {
  const count = (groups: Record<string, string[]> | undefined) => Object.values(groups ?? {}).flat().length
  const tools = count(info?.tools)
  const skills = count(info?.skills)

  const fields = [
    [
      'Profile',
      info?.profile_name && info.profile_name !== 'default' ? info.profile_name : info ? 'main' : 'Connecting…'
    ],
    [
      'Model',
      info?.model
        ? [info.model, info.provider].filter(Boolean).join(' · ')
        : info
          ? 'No model configured — /model to connect'
          : 'Loading session…'
    ],
    ['Workspace', info?.cwd || process.cwd()],
    [
      'Capabilities',
      !info || info.lazy
        ? 'Loading selected capabilities…'
        : `${tools} tools · ${skills} skills · /capabilities for details`
    ]
  ]

  return (
    <Box flexDirection="column">
      {cols >= 95 && (
        <Box flexDirection="column" marginBottom={1}>
          {art.scientist.map((line, i) => (
            <Text key={i}>
              {LOGO_COLORS.map((color, index) => (
                <Text color={color} key={color}>
                  {line.slice(
                    Math.floor((index * line.length) / LOGO_COLORS.length),
                    Math.floor(((index + 1) * line.length) / LOGO_COLORS.length)
                  )}
                </Text>
              ))}
            </Text>
          ))}
        </Box>
      )}
      <Box
        backgroundColor={t.surfaces?.elevated}
        borderColor={t.color.border}
        borderStyle="round"
        flexDirection={cols >= 85 ? 'row' : 'column'}
        marginBottom={1}
        paddingX={2}
        paddingY={1}
        width={Math.max(12, cols)}
      >
        {cols >= 85 && <BoltzmannLogo animate={animateLogo} t={t} />}
        <Box flexDirection="column" flexGrow={1} flexShrink={1}>
          <Text bold color={t.color.primary}>
            Agent Scientist
          </Text>
          <Text color={t.color.muted}>Built by Boltzmann Labs</Text>
          <Box height={1} />
          {fields.map(([label, value]) => (
            <Box flexDirection={cols < 55 ? 'column' : 'row'} key={label}>
              <Box flexShrink={0} width={cols < 55 ? undefined : 14}>
                <Text color={t.color.muted}>{label}</Text>
              </Box>
              <Box flexShrink={1}>
                <Text color={t.color.text}>{value}</Text>
              </Box>
            </Box>
          ))}
          {info?.install_warning && <Text color={t.color.warn}>{info.install_warning}</Text>}
          {typeof info?.update_behind === 'number' && info.update_behind > 0 && (
            <Text color={t.color.warn}>Update available · {info.update_command || 'sci update'}</Text>
          )}
          <Box alignItems="flex-end" flexGrow={1} justifyContent="flex-end" marginTop={1}>
            <Text color={t.color.muted}>agent-sci</Text>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}

interface ScienceMessageProps {
  children: ReactNode
  role: 'user' | 'assistant'
  cols: number
  t: Theme
  stamp?: string | null
}

export function ScienceMessage({ children, role, cols, t, stamp }: ScienceMessageProps) {
  // Outer transcript padding plus its scrollbar must fit beside the message.
  const width = Math.max(1, cols - 4)
  const response = t.surfaces?.responseBorder ?? t.color.border

  if (role === 'user') {
    return (
      <Box flexDirection="column" width={width}>
        <NoSelect>
          <Text color={t.color.sessionBorder}>{'─'.repeat(width)}</Text>
        </NoSelect>
        <Box marginTop={1}>
          <NoSelect flexShrink={0}>
            <Text bold color={t.color.accent}>
              {t.brand.prompt === DEFAULT_THEME.brand.prompt ? '● You:' : t.brand.prompt}{' '}
            </Text>
          </NoSelect>
          <Box flexDirection="column" flexShrink={1}>
            {children}
          </Box>
        </Box>
        {stamp && <Text color={t.color.muted}>{stamp}</Text>}
      </Box>
    )
  }

  const label = `─ ${t.brand.icon} ${t.brand.name.replace(/ Agent$/, '')} `

  return (
    <Box flexDirection="column" width={width}>
      <NoSelect>
        <Text color={response} wrap="truncate-end">
          {label}
          {'─'.repeat(Math.max(0, width - stringWidth(label)))}
        </Text>
      </NoSelect>
      {stamp && <Text color={t.color.muted}>{stamp}</Text>}
      <Box flexDirection="column" paddingX={1} paddingY={1}>
        {children}
      </Box>
      <NoSelect>
        <Text color={response}>{'─'.repeat(width)}</Text>
      </NoSelect>
    </Box>
  )
}
