// ─── Auth ────────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string
  token_type: string
}

// ─── Server Status ────────────────────────────────────────────────────────────
export interface ProcessStatus {
  name: string
  running: boolean
  pid?: number
  uptime_seconds?: number
  cpu_percent?: number
  memory_mb?: number
}

export interface ServerStatus {
  worldserver: ProcessStatus
  authserver: ProcessStatus
}

export interface ServerActionResponse {
  success: boolean
  message: string
}

// ─── Players ─────────────────────────────────────────────────────────────────
export interface Account {
  id: number
  username: string
  email: string
  gmlevel: number
  locked: boolean
  last_ip?: string
  last_login?: string
  banned?: boolean
}

export interface Character {
  guid: number
  account: number
  name: string
  race: number
  class: number
  level: number
  gender: number
  zone: number
  online: boolean
  money: number
}

// Race & class name maps (WoW 3.3.5a)
export const RACE_NAMES: Record<number, string> = {
  1: 'Human', 2: 'Orc', 3: 'Dwarf', 4: 'Night Elf',
  5: 'Undead', 6: 'Tauren', 7: 'Gnome', 8: 'Troll',
  10: 'Blood Elf', 11: 'Draenei',
}

export const CLASS_NAMES: Record<number, string> = {
  1: 'Warrior', 2: 'Paladin', 3: 'Hunter', 4: 'Rogue',
  5: 'Priest', 6: 'Death Knight', 7: 'Shaman', 8: 'Mage',
  9: 'Warlock', 11: 'Druid',
}

export const CLASS_COLORS: Record<number, string> = {
  1: '#C69B3A', 2: '#F58CBA', 3: '#ABD473', 4: '#FFF569',
  5: '#FFFFFF', 6: '#C41F3B', 7: '#0070DE', 8: '#69CCF0',
  9: '#9482C9', 11: '#FF7D0A',
}

// ─── Logs ────────────────────────────────────────────────────────────────────
export interface LogEntry {
  timestamp: string
  level: 'ERROR' | 'WARN' | 'INFO' | 'DEBUG' | 'FATAL' | 'TRACE' | string
  message: string
  source: string
}

export type LogSource = 'worldserver' | 'authserver' | 'gm' | 'db_errors' | 'arena' | 'char'

// ─── Database ─────────────────────────────────────────────────────────────────
export type DatabaseTarget = 'auth' | 'characters' | 'world'

export interface QueryResult {
  columns: string[]
  rows: unknown[][]
  row_count: number
  execution_time_ms: number
  is_select: boolean
}

// ─── Build ───────────────────────────────────────────────────────────────────
export interface BuildStatus {
  running: boolean
  progress_percent?: number
  current_step?: string
  elapsed_seconds?: number
  error?: string
}

// ─── Installation ─────────────────────────────────────────────────────────────
export interface InstallCheck {
  repo_cloned: boolean
  compiled: boolean
  authserver_binary: boolean
  worldserver_conf: boolean
  authserver_conf: boolean
  data_dir: boolean
  log_dir: boolean
}

// ─── Panel Settings ───────────────────────────────────────────────────────────
export interface PanelSettings {
  // Paths
  AC_PATH: string
  AC_BUILD_PATH: string
  AC_BINARY_PATH: string
  AC_CONF_PATH: string
  AC_LOG_PATH: string
  AC_DATA_PATH: string
  AC_WORLDSERVER_CONF: string
  AC_AUTHSERVER_CONF: string
  // Auth DB
  AC_AUTH_DB_HOST: string
  AC_AUTH_DB_PORT: string
  AC_AUTH_DB_USER: string
  AC_AUTH_DB_PASSWORD: string
  AC_AUTH_DB_NAME: string
  // Characters DB
  AC_CHAR_DB_HOST: string
  AC_CHAR_DB_PORT: string
  AC_CHAR_DB_USER: string
  AC_CHAR_DB_PASSWORD: string
  AC_CHAR_DB_NAME: string
  // World DB
  AC_WORLD_DB_HOST: string
  AC_WORLD_DB_PORT: string
  AC_WORLD_DB_USER: string
  AC_WORLD_DB_PASSWORD: string
  AC_WORLD_DB_NAME: string
  // SOAP
  AC_SOAP_HOST: string
  AC_SOAP_PORT: string
  AC_SOAP_USER: string
  AC_SOAP_PASSWORD: string
  // Remote Access
  AC_RA_HOST: string
  AC_RA_PORT: string
}

