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

// ─── Worldserver Instances ────────────────────────────────────────────────────
export interface WorldServerInstance {
  id: number
  display_name: string
  process_name: string
  binary_path: string
  working_dir: string
  conf_path: string
  notes: string
  sort_order: number
  // Per-instance AC installation overrides (empty = use global)
  ac_path: string
  build_path: string
  // Per-instance characters DB overrides (empty = use global)
  char_db_host: string
  char_db_port: string
  char_db_user: string
  char_db_password: string
  char_db_name: string
  // Per-instance SOAP overrides (empty = use global)
  soap_host: string
  soap_port: string
  soap_user: string
  soap_password: string
  status?: ProcessStatus
}

export interface WorldServerInstanceCreate {
  display_name: string
  process_name: string
  binary_path?: string
  working_dir?: string
  conf_path?: string
  notes?: string
  sort_order?: number
  ac_path?: string
  build_path?: string
  char_db_host?: string
  char_db_port?: string
  char_db_user?: string
  char_db_password?: string
  char_db_name?: string
  soap_host?: string
  soap_port?: string
  soap_user?: string
  soap_password?: string
}

export interface WorldServerInstanceUpdate {
  display_name?: string
  binary_path?: string
  working_dir?: string
  conf_path?: string
  notes?: string
  sort_order?: number
  ac_path?: string
  build_path?: string
  char_db_host?: string
  char_db_port?: string
  char_db_user?: string
  char_db_password?: string
  char_db_name?: string
  soap_host?: string
  soap_port?: string
  soap_user?: string
  soap_password?: string
}

export interface WorldServerProvisionRequest {
  conf_output_path: string
  realm_name?: string
  worldserver_port?: number
  instance_port?: number
  ra_port?: number
  realm_id?: number
  realm_address?: string
  extra_overrides?: Record<string, string>
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

// Zone names (WoW 3.3.5a - Eastern Kingdoms, Kalimdor, Outland, Northrend)
// This is a partial list of common zones
export const ZONE_NAMES: Record<number, string> = {
  // Eastern Kingdoms
  1: 'Dun Morogh', 3: 'Badlands', 4: 'Blasted Lands', 7: 'Blackrock Mountain',
  8: 'Swamp of Sorrows', 9: 'Elwynn Forest', 10: 'Eversong Woods', 11: 'Ghostlands',
  12: 'Ironforge', 14: 'Durotar', 15: 'Dustwallow Marsh', 16: 'Azshara',
  17: 'The Barrens', 22: 'Wetlands', 23: 'Duskwood', 24: 'Hillsbrad Foothills',
  25: 'The Hinterlands', 26: 'Feralas', 27: 'Thousand Needles', 28: 'Tanaris',
  32: 'Searing Gorge', 33: 'Stranglethorn Vale', 36: 'Alterac Mountains',
  38: 'Loch Modan', 40: 'Westfall', 41: 'Deadwind Pass', 42: 'Darkshore',
  43: 'Ashenvale', 44: 'Thousand Needles', 45: 'Arathi Highlands', 46: 'Burning Steppes',
  47: 'The Hinterlands', 48: 'Redridge Mountains', 51: 'Searing Gorge',
  65: 'Dragonblight', 66: 'Zul\'Drak', 67: 'The Storm Peaks', 68: 'Icecrown',
  69: 'Howling Fjord', 70: 'Grizzly Hills', 71: 'Sholazar Basin', 72: 'Borean Tundra',
  85: 'Tirisfal Glades', 86: 'Silverpine Forest', 87: 'Western Plaguelands',
  88: 'Eastern Plaguelands', 89: 'Scarlet Monastery', 90: 'Teldrassil',
  92: 'Molten Core', 93: 'Zul\'Gurub', 94: 'Stratholme', 95: 'Scholomance',
  101: 'Darnassus', 102: 'Ironforge', 103: 'Orgrimmar', 104: 'Thunder Bluff',
  105: 'Undercity', 106: 'Silvermoon City', 107: 'Exodar', 108: 'Shattrath City',
  109: 'Dalaran',
  // Outland
  194: 'Shadowmoon Valley', 195: 'Nagrand', 196: 'Terokkar Forest',
  197: 'Zangarmarsh', 198: 'Blade\'s Edge Mountains', 199: 'Netherstorm',
  200: 'Hellfire Peninsula', 201: 'Shattrath City',
  // Northrend
  341: 'Wintergrasp', 394: 'Grizzly Hills', 395: 'Howling Fjord',
  396: 'Icecrown', 397: 'Sholazar Basin', 398: 'Zul\'Drak',
  399: 'The Storm Peaks', 400: 'Dragonblight', 401: 'Borean Tundra',
  402: 'Crystalsong Forest', 419: 'Dalaran',
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
  // present on browse (table scan) responses
  total?: number
  page?: number
  page_size?: number
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

// ─── Module Manager ───────────────────────────────────────────────────────────
export interface CatalogueModule {
  id: number
  name: string
  full_name: string
  description: string
  html_url: string
  clone_url: string
  ssh_url: string
  stars: number
  forks: number
  open_issues: number
  default_branch: string
  updated_at: string
  pushed_at: string
  archived: boolean
  topics: string[]
  owner_avatar: string
  owner_login: string
  installed: boolean
}

export interface CatalogueResponse {
  total_count: number
  page: number
  per_page: number
  items: CatalogueModule[]
}

export interface InstalledModule {
  name: string
  path: string
  has_git: boolean
  remote_url: string | null
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
  AC_CLIENT_PATH: string
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
  // GitHub
  GITHUB_TOKEN: string
}

// ─── Backup & Restore ────────────────────────────────────────────────────────

export type BackupDestType = 'local' | 'sftp' | 'ftp' | 's3' | 'gdrive' | 'onedrive'

// Config shapes per destination type (all fields are strings to keep form-binding simple)
export interface LocalConfig { path: string }
export interface SftpConfig  { host: string; port: string; username: string; password: string; private_key: string; path: string }
export interface FtpConfig   { host: string; port: string; username: string; password: string; path: string; tls: boolean }
export interface S3Config    { access_key_id: string; secret_access_key: string; bucket: string; region: string; prefix: string }
export interface GDriveConfig  { service_account_json: string; folder_id: string }
export interface OneDriveConfig { client_id: string; client_secret: string; tenant_id: string; folder_path: string; drive_id: string }

export interface BackupDestination {
  id: number
  name: string
  type: BackupDestType
  config: Record<string, unknown>
  enabled: boolean
  created_at: string
}

export interface BackupJob {
  id: number
  destination_id: number | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  include_configs: boolean
  include_databases: boolean
  include_server_files: boolean
  filename: string
  local_path: string
  size_bytes: number
  started_at: string
  completed_at: string
  error: string
  notes: string
}

export interface BackupFile {
  filename: string
  size_bytes: number
  modified: string
}

export interface BackupDestinationCreate {
  name: string
  type: BackupDestType
  config: Record<string, unknown>
  enabled: boolean
}

export interface BackupJobCreate {
  destination_id?: number | null
  include_configs: boolean
  include_databases: boolean
  include_server_files: boolean
  notes: string
}


