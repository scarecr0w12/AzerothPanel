import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ap_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ap_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login/json', { username, password }),
  me: () => api.get('/auth/me'),
}

// ─── Server ──────────────────────────────────────────────────────────────────
export const serverApi = {
  status: () => api.get('/server/status'),
  startWorld: () => api.post('/server/worldserver/start'),
  stopWorld: () => api.post('/server/worldserver/stop'),
  restartWorld: () => api.post('/server/worldserver/restart'),
  startAuth: () => api.post('/server/authserver/start'),
  stopAuth: () => api.post('/server/authserver/stop'),
  restartAuth: () => api.post('/server/authserver/restart'),
  command: (command: string) => api.post('/server/command', { command }),
  info: () => api.get('/server/info'),
  announce: (message: string) => api.post('/server/announce', { command: message }),
}

// ─── Worldserver Instances ────────────────────────────────────────────────────
export const instancesApi = {
  list: () => api.get('/server/instances'),
  get: (id: number) => api.get(`/server/instances/${id}`),
  create: (data: import('@/types').WorldServerInstanceCreate) =>
    api.post('/server/instances', data),
  update: (id: number, data: import('@/types').WorldServerInstanceUpdate) =>
    api.put(`/server/instances/${id}`, data),
  delete: (id: number) => api.delete(`/server/instances/${id}`),
  start: (id: number) => api.post(`/server/instances/${id}/start`),
  stop: (id: number) => api.post(`/server/instances/${id}/stop`),
  restart: (id: number) => api.post(`/server/instances/${id}/restart`),
  command: (id: number, command: string) =>
    api.post(`/server/instances/${id}/command`, { command }),
  getConfig: (id: number) => api.get(`/server/instances/${id}/config`),
  saveConfig: (id: number, content: string) =>
    api.put(`/server/instances/${id}/config`, { content }),
  generateConfig: (id: number, data: import('@/types').WorldServerProvisionRequest) =>
    api.post(`/server/instances/${id}/generate-config`, data),
}

// ─── Logs ────────────────────────────────────────────────────────────────────
export const logsApi = {
  sources: () => api.get('/logs/sources'),
  tail: (source: string, lines = 500) => api.get(`/logs/${source}`, { params: { lines } }),
  search: (source: string, search: string, level?: string) =>
    api.get(`/logs/${source}`, { params: { search, level } }),
  download: (source: string) => `/api/v1/logs/${source}/download`,
}

// ─── Players ─────────────────────────────────────────────────────────────────
export const playersApi = {
  online: () => api.get('/players/online'),
  accounts: (search?: string, page = 1) =>
    api.get('/players/accounts', { params: { search, page } }),
  characters: (search?: string, onlineOnly = false, page = 1) =>
    api.get('/players/characters', { params: { search, online_only: onlineOnly, page } }),
  character: (guid: number) => api.get(`/players/characters/${guid}`),
  ban: (account_id: number, duration: string, reason: string) =>
    api.post('/players/ban', { account_id, duration, reason }),
  unban: (account_id: number) => api.post(`/players/unban/${account_id}`),
  kick: (name: string) => api.post(`/players/kick/${name}`),
  announce: (message: string, target = 'all') =>
    api.post('/players/announce', { message, target }),
  modify: (guid: number, field: string, value: unknown) =>
    api.post('/players/modify', { guid, field, value }),
}

// ─── Database ─────────────────────────────────────────────────────────────────
export const dbApi = {
  available: () => api.get<{ databases: string[] }>('/database/available'),

  tables: (database: string) => api.get(`/database/tables/${database}`),

  schema: (database: string, table: string) =>
    api.get(`/database/schema/${database}/${table}`),

  query: (database: string, query: string, max_rows = 500) =>
    api.post('/database/query', { database, query, max_rows }),

  browse: (
    database: string,
    table: string,
    page = 1,
    order_by?: string,
    order_dir: 'asc' | 'desc' = 'asc',
    filters?: string,
  ) =>
    api.get(`/database/table/${database}/${table}`, {
      params: { page, order_by, order_dir, filters },
    }),

  insertRow: (database: string, table: string, data: Record<string, unknown>) =>
    api.post('/database/row', { database, table, data }),

  updateRow: (
    database: string,
    table: string,
    pk_columns: Record<string, unknown>,
    data: Record<string, unknown>,
  ) => api.put('/database/row', { database, table, pk_columns, data }),

  deleteRow: (
    database: string,
    table: string,
    pk_columns: Record<string, unknown>,
  ) => api.delete('/database/row', { data: { database, table, pk_columns } }),

  export: (database: string, query: string, format: 'csv' | 'json', max_rows = 100_000) =>
    api.post('/database/export', { database, query, format, max_rows }, { responseType: 'blob' }),

  backup: (database: string) =>
    api.post('/database/backup', null, { params: { database } }),
}

// ─── Installation ─────────────────────────────────────────────────────────────
export const installApi = {
  status: () => api.get('/installation/status'),
  worldserverConf: () => api.get('/installation/config/worldserver'),
  saveWorldserverConf: (content: string) =>
    api.put('/installation/config/worldserver', { content }),
  authserverConf: () => api.get('/installation/config/authserver'),
  saveAuthserverConf: (content: string) =>
    api.put('/installation/config/authserver', { content }),
}

// ─── Compilation ─────────────────────────────────────────────────────────────
export const compileApi = {
  status: () => api.get('/compilation/status'),
  /**
   * Start a build and return the raw fetch Response (SSE stream).
   * The caller is responsible for reading response.body.
   */
  build: (
    buildType: string,
    jobs: number,
    cmakeExtra: string,
    signal?: AbortSignal,
  ) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/compilation/build', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ build_type: buildType, jobs, cmake_extra: cmakeExtra }),
      signal,
    })
  },
}

// ─── Settings ─────────────────────────────────────────────────────────────────
export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data: Record<string, string>) => api.put('/settings', data),
  testDb: (data: {
    host: string
    port: string
    user: string
    password: string
    db_name: string
  }) => api.post('/settings/test-db', data),
  panelVersion: () => api.get('/settings/panel-version'),
  updatePanel: () => api.post('/settings/update-panel'),
}

// ─── Installation (streaming) ──────────────────────────────────────────────────
export const installStreamApi = {
  /**
   * Start the installation and return the raw fetch Response (SSE stream).
   */
  run: (
    config: {
      ac_path: string
      db_host: string
      db_user: string
      db_password: string
      clone_branch: string
      repository_url: string
    },
    signal?: AbortSignal,
  ) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/installation/run', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(config),
      signal,
    })
  },
}

// ─── Modules ─────────────────────────────────────────────────────────────────
export const modulesApi = {
  catalogue: (category = 'modules', page = 1, perPage = 30) =>
    api.get('/modules/catalogue', { params: { category, page, per_page: perPage } }),

  installed: () => api.get('/modules/installed'),

  rateLimit: () => api.get('/modules/github/rate-limit'),

  /**
   * Stream git clone output as SSE.
   */
  install: (clone_url: string, module_name: string, branch?: string, signal?: AbortSignal) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/modules/install', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ clone_url, module_name, branch: branch ?? null }),
      signal,
    })
  },

  remove: (moduleName: string) =>
    api.delete(`/modules/${encodeURIComponent(moduleName)}`),

  /** Stream git pull output for the AzerothCore source tree. */
  updateAzerothCore: (signal?: AbortSignal) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/modules/update-azerothcore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      signal,
    })
  },

  /** Stream git pull output for a single installed module. */
  updateModule: (moduleName: string, signal?: AbortSignal) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch(`/api/v1/modules/${encodeURIComponent(moduleName)}/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      signal,
    })
  },

  /** Stream git pull output for all installed git-tracked modules. */
  updateAll: (signal?: AbortSignal) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/modules/update-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      signal,
    })
  },
}

// ─── Config Files ─────────────────────────────────────────────────────────────
// rel can contain '/' (e.g. "modules/mod_something.conf") – encode each segment.
const _confPath = (rel: string) =>
  rel.split('/').map(encodeURIComponent).join('/')

export const configsApi = {
  list: () => api.get('/configs'),
  get: (rel: string) => api.get(`/configs/${_confPath(rel)}`),
  save: (rel: string, content: string) =>
    api.put(`/configs/${_confPath(rel)}`, { content }),
}

// ─── Data Extraction ─────────────────────────────────────────────────────────
export const dataExtractionApi = {
  status: () => api.get('/data-extraction/status'),
  cancel: () => api.post('/data-extraction/cancel'),
  /**
   * Download pre-extracted data and return the raw fetch Response (SSE stream).
   */
  download: (dataPath?: string, dataUrl?: string, signal?: AbortSignal) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/data-extraction/download', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ data_path: dataPath, data_url: dataUrl }),
      signal,
    })
  },
  /**
   * Extract from local client and return the raw fetch Response (SSE stream).
   */
  extract: (
    config: {
      client_path?: string
      data_path?: string
      binary_path?: string
      extract_dbc?: boolean
      extract_maps?: boolean
      extract_vmaps?: boolean
      generate_mmaps?: boolean
    },
    signal?: AbortSignal,
  ) => {
    const token = localStorage.getItem('ap_token') ?? ''
    return fetch('/api/v1/data-extraction/extract', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(config),
      signal,
    })
  },
}

