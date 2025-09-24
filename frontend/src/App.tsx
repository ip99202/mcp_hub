import { useEffect, useRef, useState } from 'react'
import './App.css'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

function App() {
  // Server form state
  const [serverName, setServerName] = useState('Weather API')
  const [serverBaseUrl, setServerBaseUrl] = useState('https://api.weather.com/v1')
  const [authType, setAuthType] = useState('none')
  const [authKey, setAuthKey] = useState('')
  const [authValue, setAuthValue] = useState('')
  const [defaultHeaders, setDefaultHeaders] = useState('{"Accept": "application/json"}')
  const [serverActive, setServerActive] = useState(true)

  // Tool form state
  const [selectedServerId, setSelectedServerId] = useState('')
  const [toolName, setToolName] = useState('get_forecast')
  const [toolDescription, setToolDescription] = useState('국가/도시 기준 단기 예보 조회')
  const [httpMethod, setHttpMethod] = useState('GET')
  const [pathTemplate, setPathTemplate] = useState('/forecast/{country}')
  const [inputSchemaText, setInputSchemaText] = useState('{\n  "type": "object",\n  "properties": {\n    "country": {"type": "string"},\n    "city": {"type": "string"},\n    "days": {"type": "integer", "default": 3}\n  },\n  "required": ["country", "city"]\n}')
  const [pathMapText, setPathMapText] = useState('{"country": "country"}')
  const [queryMapText, setQueryMapText] = useState('{"city": "city", "days": "days"}')
  const [headersMapText, setHeadersMapText] = useState('{}')
  const [bodyMapText, setBodyMapText] = useState('{}')
  const [rawBodyKey, setRawBodyKey] = useState('')
  const [responsePick, setResponsePick] = useState('$.forecast.daily')
  const [toolActive, setToolActive] = useState(true)
  
  // Edit states
  const [editingServerId, setEditingServerId] = useState('')
  const [editingToolName, setEditingToolName] = useState('')
  const [editingToolServerId, setEditingToolServerId] = useState('')

  // Legacy state for compatibility
  const [serverId, setServerId] = useState('demo')
  const [baseUrl, setBaseUrl] = useState('https://api.ipify.org')
  const [args, setArgs] = useState('{"format":"json"}')
  const [servers, setServers] = useState<Record<string, any>>({})
  const [tools, setTools] = useState<Record<string, any>>({})
  const [stats, setStats] = useState<{ servers: number; tools: number; activeServers?: number; activeTools?: number }>({ servers: 0, tools: 0 })

  const [log, setLog] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  const [testDialogOpen, setTestDialogOpen] = useState(false)
  const [testLog, setTestLog] = useState<string[]>([])
  const [isTesting, setIsTesting] = useState(false)
  const [testingTarget, setTestingTarget] = useState<{ serverId: string; toolName: string } | null>(null)

  const [serverDialogOpen, setServerDialogOpen] = useState(false)
  const [toolDialogOpen, setToolDialogOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'servers' | 'tools'>('servers')

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [log, testLog])

  const post = async (path: string, body: any) => {
    const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    return res.json()
  }

  const del = async (path: string) => {
    const res = await fetch(path, { method: 'DELETE' })
    return res.json()
  }

  const getJson = async (path: string) => {
    const res = await fetch(path)
    return res.json()
  }

  const refreshStats = async () => {
    try {
      const data = await getJson('/api/stats')
      setStats({ 
        servers: data?.servers || 0, 
        tools: data?.tools || 0,
        activeServers: data?.activeServers ?? undefined,
        activeTools: data?.activeTools ?? undefined,
      })
    } catch (e) {
      setStats({ servers: Object.keys(servers).length, tools: Object.keys(tools).length, activeServers: undefined, activeTools: undefined })
    }
  }

  const upsertServer = async () => {
    let auth: any = undefined
    let headers: any = undefined
    
    try {
      if (authType !== 'none' && authKey && authValue) {
        auth = { type: authType, key: authKey, value: authValue }
      }
      headers = defaultHeaders ? JSON.parse(defaultHeaders) : {}
    } catch (e: any) {
      setLog((l) => [...l, `error: invalid JSON - ${e?.message || e}`])
      return
    }

    const body = { 
      name: serverName,
      baseUrl: serverBaseUrl, 
      auth,
      defaultHeaders: headers,
      active: serverActive 
    }
    const serverIdToUse = editingServerId || serverName.toLowerCase().replace(/\s+/g, '_')
    await post(`/api/servers/${serverIdToUse}`, body)
    setLog((l) => [...l, `server ${editingServerId ? 'updated' : 'created'}: ${serverName}`])
    await refreshServers()
    await refreshStats()
  }

  const upsertTool = async () => {
    let inputSchema: any = undefined
    let pathMap: any = undefined
    let queryMap: any = undefined
    let headersMap: any = undefined
    let bodyMap: any = undefined
    
    try {
      inputSchema = inputSchemaText ? JSON.parse(inputSchemaText) : { type: 'object' }
    } catch (e: any) {
      setLog((l) => [...l, `error: invalid inputSchema JSON - ${e?.message || e}`])
      return
    }
    try {
      pathMap = pathMapText ? JSON.parse(pathMapText) : {}
      queryMap = queryMapText ? JSON.parse(queryMapText) : {}
      headersMap = headersMapText ? JSON.parse(headersMapText) : {}
      bodyMap = bodyMapText ? JSON.parse(bodyMapText) : {}
    } catch (e: any) {
      setLog((l) => [...l, `error: invalid param mapping JSON - ${e?.message || e}`])
      return
    }

    const body: any = {
      name: toolName,
      description: toolDescription,
      method: httpMethod,
      pathTemplate: pathTemplate,
      paramMapping: { 
        path: pathMap || {}, 
        query: queryMap || {}, 
        headers: headersMap || {}, 
        body: bodyMap || {}, 
        rawBody: rawBodyKey || undefined 
      },
      inputSchema: inputSchema || { type: 'object' },
      active: toolActive,
    }
    if (responsePick && responsePick.trim().length > 0) {
      body.responseMapping = { pick: responsePick.trim() }
    }
    const serverToUse = editingToolServerId || selectedServerId
    if (!serverToUse) {
      setLog((l) => [...l, `error: no server selected`])
      return
    }
    const toolNameToUse = editingToolName || toolName
    await post(`/api/tools/${serverToUse}/${toolNameToUse}`, body)
    setLog((l) => [...l, `tool ${editingToolName ? 'updated' : 'created'}: ${toolName}`])
    await refreshTools(serverToUse)
    await refreshStats()
  }

  const callSSE = async () => {
    setLog((l) => [...l, `calling /mcp/${serverId}/${toolName} ...`])
    const es = new EventSource(`/mcp/${serverId}/${toolName}`, { withCredentials: false })
    // EventSource with POST is not standard; fallback via fetch + ReadableStream if needed. We'll use fetch stream.
    es.close()

    try {
      const res = await fetch(`/mcp/${serverId}/${toolName}`, {
        method: 'POST',
        headers: { 'Accept': 'text/event-stream', 'Content-Type': 'application/json' },
        body: JSON.stringify({ args: JSON.parse(args || '{}') }),
      })
      if (!res.body) throw new Error('no body')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        setLog((l) => [...l, ...chunk.trim().split('\n').map((s) => s)])
      }
      setLog((l) => [...l, 'stream closed'])
    } catch (e: any) {
      setLog((l) => [...l, `error: ${e?.message || e}`])
    }
  }


  const activeServers = stats.activeServers ?? Object.values(servers).filter((s: any) => s.active).length
  const activeTools = stats.activeTools ?? Object.values(tools).filter((t: any) => t.active).length

  const refreshServers = async () => {
    const data = await getJson('/api/servers')
    setServers(data || {})
  }

  const refreshTools = async (targetServerId?: string) => {
    try {
      const serverToUse = targetServerId || selectedServerId
      console.log('refreshTools:', { targetServerId, selectedServerId, serverToUse, serversCount: Object.keys(servers).length })
      
      if (!serverToUse || serverToUse === "__all__") {
        // 서버가 선택되지 않은 경우 모든 서버의 툴을 가져오기
        console.log('Loading all tools from servers:', Object.keys(servers))
        const allTools: any = {}
        const serverEntries = Object.entries(servers)
        
        for (const [serverId] of serverEntries) {
          try {
            console.log(`Fetching tools for server: ${serverId}`)
            const data = await getJson(`/api/tools/${serverId}`)
            console.log(`Tools from ${serverId}:`, data)
            Object.entries(data || {}).forEach(([toolName, binding]: [string, any]) => {
              allTools[`${serverId}::${toolName}`] = { ...binding, serverId }
            })
          } catch (e) {
            console.warn(`Failed to load tools for ${serverId}:`, e)
          }
        }
        console.log('All tools loaded:', allTools)
        setTools(allTools)
        return
      }
      console.log(`Loading tools for specific server: ${serverToUse}`)
      const data = await getJson(`/api/tools/${serverToUse}`)
      console.log(`Tools from ${serverToUse}:`, data)
      setTools(data || {})
    } catch (error) {
      console.error('Failed to refresh tools:', error)
      setTools({})
    }
  }

  const selectServer = async (id: string) => {
    setServerId(id)
    const cfg = await getJson(`/api/servers/${id}`)
    setBaseUrl(cfg?.baseUrl || '')
    await refreshTools()
  }

  const deleteServer = async (id: string) => {
    const ok = window.confirm(`서버 "${id}"를 삭제하시겠습니까?`)
    if (!ok) return
    await del(`/api/servers/${id}`)
    if (id === serverId) setTools({})
    await refreshServers()
    await refreshStats()
  }

  const deleteTool = async (name: string, toolServerId?: string) => {
    const serverToUse = toolServerId || selectedServerId
    if (!serverToUse) return
    const ok = window.confirm(`툴 "${name}"를 삭제하시겠습니까?`)
    if (!ok) return
    await del(`/api/tools/${serverToUse}/${name}`)
    await refreshTools(selectedServerId || undefined)
    await refreshStats()
  }

  const editServer = async (id: string) => {
    const cfg = await getJson(`/api/servers/${id}`)
    setEditingServerId(id)
    setServerName(cfg.name || id)
    setServerBaseUrl(cfg.baseUrl || '')
    setAuthType(cfg.auth?.type || 'none')
    setAuthKey(cfg.auth?.key || '')
    setAuthValue(cfg.auth?.value || '')
    setDefaultHeaders(JSON.stringify(cfg.defaultHeaders || {}, null, 2))
    setServerActive(cfg.active !== false)
    setServerDialogOpen(true)
  }

  const editTool = async (toolName: string, serverId: string) => {
    const binding = await getJson(`/api/tools/${serverId}/${toolName}`)
    setEditingToolName(toolName)
    setEditingToolServerId(serverId)
    setSelectedServerId(serverId)
    setToolName(binding.name || toolName)
    setToolDescription(binding.description || '')
    setHttpMethod(binding.method || 'GET')
    setPathTemplate(binding.pathTemplate || '/')
    setInputSchemaText(JSON.stringify(binding.inputSchema || {type: 'object'}, null, 2))
    setPathMapText(JSON.stringify(binding.paramMapping?.path || {}, null, 2))
    setQueryMapText(JSON.stringify(binding.paramMapping?.query || {}, null, 2))
    setHeadersMapText(JSON.stringify(binding.paramMapping?.headers || {}, null, 2))
    setBodyMapText(JSON.stringify(binding.paramMapping?.body || {}, null, 2))
    setRawBodyKey(binding.paramMapping?.rawBody || '')
    setResponsePick(binding.responseMapping?.pick || '')
    setToolActive(binding.active !== false)
    setToolDialogOpen(true)
  }

  const testTool = async (toolName: string, serverId: string) => {
    if (isTesting) return
    setIsTesting(true)
    setTestingTarget({ serverId, toolName })
    setTestLog([`testing tool: ${serverId}/${toolName}...`])
    setTestDialogOpen(true)
    try {
      const res = await fetch(`/mcp/${serverId}/${toolName}`, {
        method: 'POST',
        headers: { 
          'Accept': 'text/event-stream',
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify({ args: {} })
      })
      
      if (!res.body) {
        setTestLog((l) => [...l, 'error: no response body'])
        setIsTesting(false)
        return
      }
      
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.trim().split('\n')
        for (const line of lines) {
          if (line.trim()) {
            setTestLog((l) => [...l, line])
          }
        }
      }
      setTestLog((l) => [...l, 'test completed'])
    } catch (e: any) {
      setTestLog((l) => [...l, `error: ${e?.message || e}`])
    } finally {
      setIsTesting(false)
    }
  }

  const clearForm = () => {
    setEditingServerId('')
    setEditingToolName('')
    setEditingToolServerId('')
    setServerName('Weather API')
    setServerBaseUrl('https://api.weather.com/v1')
    setAuthType('none')
    setAuthKey('')
    setAuthValue('')
    setDefaultHeaders('{"Accept": "application/json"}')
    setServerActive(true)
    setSelectedServerId('')
    setToolName('get_forecast')
    setToolDescription('국가/도시 기준 단기 예보 조회')
    setHttpMethod('GET')
    setPathTemplate('/forecast/{country}')
    setInputSchemaText('{\n  "type": "object",\n  "properties": {\n    "country": {"type": "string"},\n    "city": {"type": "string"},\n    "days": {"type": "integer", "default": 3}\n  },\n  "required": ["country", "city"]\n}')
    setPathMapText('{"country": "country"}')
    setQueryMapText('{"city": "city", "days": "days"}')
    setHeadersMapText('{}')
    setBodyMapText('{}')
    setRawBodyKey('')
    setResponsePick('$.forecast.daily')
    setToolActive(true)
  }


  // LocalStorage load
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('mcp_hub_ui') || '{}')
      if (saved.serverId) setServerId(saved.serverId)
      if (saved.baseUrl) setBaseUrl(saved.baseUrl)
      if (saved.toolName) setToolName(saved.toolName)
      if (saved.args) setArgs(saved.args)
      if (saved.responsePick) setResponsePick(saved.responsePick)
    } catch {}
  }, [])

  // LocalStorage save
  useEffect(() => {
    const payload = { serverId, baseUrl, toolName, args, responsePick }
    localStorage.setItem('mcp_hub_ui', JSON.stringify(payload))
  }, [serverId, baseUrl, toolName, args, responsePick])

  useEffect(() => {
    refreshServers()
    refreshStats()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    // 서버 목록이 로드되면 툴 목록도 즉시 동기화하여
    // 상단 Summary의 Tools 카운트가 0으로 보이지 않도록 한다
    if (Object.keys(servers).length > 0) {
      refreshTools(selectedServerId || undefined)
    } else {
      setTools({})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [servers, selectedServerId])

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-6">
      <h1 className="text-3xl font-bold mb-6">MCP Hub Dashboard</h1>
      
      {/* Summary Cards */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card className="bg-white border border-gray-200">
          <CardContent className="p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Servers</div>
            <div className="text-3xl font-bold text-gray-900">{stats.servers}</div>
            <div className="text-sm text-gray-500">{activeServers} active</div>
          </CardContent>
        </Card>
        <Card className="bg-white border border-gray-200">
          <CardContent className="p-6">
            <div className="text-sm font-medium text-gray-600 mb-1">Tools</div>
            <div className="text-3xl font-bold text-gray-900">{stats.tools}</div>
            <div className="text-sm text-gray-500">{activeTools} active</div>
          </CardContent>
        </Card>
      </div>

      {/* Navigation Tabs */}
      <div className="flex gap-2 mb-6">
        <Button 
          variant={activeTab === 'servers' ? 'default' : 'outline'}
          onClick={() => setActiveTab('servers')}
          className={activeTab === 'servers' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border-gray-300'}
        >
          Servers
        </Button>
        <Button 
          variant={activeTab === 'tools' ? 'default' : 'outline'}
          onClick={() => setActiveTab('tools')}
          className={activeTab === 'tools' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border-gray-300'}
        >
          Tools
        </Button>
      </div>

      {/* Main Content */}
      {activeTab === 'servers' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">MCP Servers</h2>
            <Dialog open={serverDialogOpen} onOpenChange={(open) => { setServerDialogOpen(open); if (!open) clearForm(); }}>
              <DialogTrigger asChild>
                <Button className="bg-blue-600 hover:bg-blue-600/90">+ Add Server</Button>
              </DialogTrigger>
              <DialogContent className="bg-white text-gray-900 border-gray-200 max-w-2xl">
                <DialogHeader>
                  <DialogTitle>{editingServerId ? 'Edit Server' : 'Add Server'}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="serverName">Server Name *</Label>
                    <Input id="serverName" className="mt-1" value={serverName} onChange={(e) => setServerName(e.target.value)} placeholder="Weather API" />
                  </div>
                  <div>
                    <Label htmlFor="serverBaseUrl">Base URL *</Label>
                    <Input id="serverBaseUrl" className="mt-1" value={serverBaseUrl} onChange={(e) => setServerBaseUrl(e.target.value)} placeholder="https://api.weather.com/v1" />
                  </div>
                  <div>
                    <Label htmlFor="authType">Authentication</Label>
                    <Select value={authType} onValueChange={setAuthType}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Select auth type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        <SelectItem value="bearer">Bearer Token</SelectItem>
                        <SelectItem value="header">Header</SelectItem>
                        <SelectItem value="query">Query Parameter</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {authType !== 'none' && (
                    <>
                      <div>
                        <Label htmlFor="authKey">Auth Key</Label>
                        <Input id="authKey" className="mt-1" value={authKey} onChange={(e) => setAuthKey(e.target.value)} placeholder="X-API-Key" />
                      </div>
                      <div>
                        <Label htmlFor="authValue">Auth Value</Label>
                        <Input id="authValue" className="mt-1" type="password" value={authValue} onChange={(e) => setAuthValue(e.target.value)} placeholder="abc123" />
                      </div>
                    </>
                  )}
                  <div>
                    <Label htmlFor="defaultHeaders">Default Headers (JSON)</Label>
                    <Textarea id="defaultHeaders" className="mt-1 font-mono text-sm" value={defaultHeaders} onChange={(e) => setDefaultHeaders(e.target.value)} placeholder='{"Accept": "application/json"}' />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch id="serverActive" checked={serverActive} onCheckedChange={setServerActive} />
                    <Label htmlFor="serverActive">Active</Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setServerDialogOpen(false)}>Cancel</Button>
                  <Button className="bg-blue-600 hover:bg-blue-600/90" onClick={async () => { await upsertServer(); setServerDialogOpen(false); clearForm(); }}>
                    {editingServerId ? 'Update' : 'Save'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="space-y-4">
            {Object.entries(servers).map(([id, cfg]) => (
              <Card key={id} className="bg-white border border-gray-200">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-gray-900">{id}</h3>
                          <span className={`px-2 py-1 text-xs rounded-full ${cfg.active ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-600'}`}>
                            {cfg.active ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mb-1">REST API Server</p>
                        <p className="text-sm text-gray-500">{cfg.baseUrl}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => editServer(id)}>Edit</Button>
                      <Button variant="outline" size="sm" onClick={() => deleteServer(id)}>Delete</Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {Object.entries(servers).length === 0 && (
              <Card className="bg-white border border-gray-200">
                <CardContent className="p-12 text-center">
                  <p className="text-gray-500">No servers configured</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {activeTab === 'tools' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold">MCP Tools ({Object.keys(tools).length})</h2>
              <Select value={selectedServerId || "__all__"} onValueChange={(serverId) => { 
                const actualServerId = serverId === "__all__" ? "" : serverId;
                setSelectedServerId(actualServerId); 
                refreshTools(actualServerId || undefined); 
              }}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="All tools" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Servers</SelectItem>
                  {Object.entries(servers).map(([id, cfg]) => (
                    <SelectItem key={id} value={id}>{cfg.name || id}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Dialog open={toolDialogOpen} onOpenChange={(open) => { setToolDialogOpen(open); if (!open) clearForm(); }}>
              <DialogTrigger asChild>
                <Button className="bg-blue-600 hover:bg-blue-600/90">+ Add Tool</Button>
              </DialogTrigger>
              <DialogContent className="bg-white text-gray-900 border-gray-200 max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>{editingToolName ? 'Edit Tool' : 'Add Tool'}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="selectedServerId">Server *</Label>
                    <Select value={selectedServerId} onValueChange={setSelectedServerId}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Select server" />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(servers).map(([id, cfg]) => (
                          <SelectItem key={id} value={id}>{cfg.name || id}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="toolName">Tool Name *</Label>
                      <Input id="toolName" className="mt-1" value={toolName} onChange={(e) => setToolName(e.target.value)} placeholder="get_forecast" />
                    </div>
                    <div>
                      <Label htmlFor="httpMethod">HTTP Method *</Label>
                      <Select value={httpMethod} onValueChange={setHttpMethod}>
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="Select method" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="GET">GET</SelectItem>
                          <SelectItem value="POST">POST</SelectItem>
                          <SelectItem value="PUT">PUT</SelectItem>
                          <SelectItem value="PATCH">PATCH</SelectItem>
                          <SelectItem value="DELETE">DELETE</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="toolDescription">Description</Label>
                    <Textarea id="toolDescription" className="mt-1" value={toolDescription} onChange={(e) => setToolDescription(e.target.value)} placeholder="국가/도시 기준 단기 예보 조회" />
                  </div>
                  <div>
                    <Label htmlFor="pathTemplate">Path Template *</Label>
                    <Input id="pathTemplate" className="mt-1 font-mono text-sm" value={pathTemplate} onChange={(e) => setPathTemplate(e.target.value)} placeholder="/forecast/{country}" />
                  </div>
                  <div>
                    <Label htmlFor="inputSchemaText">Input Schema (JSON Schema) *</Label>
                    <Textarea id="inputSchemaText" className="mt-1 font-mono text-sm h-32" value={inputSchemaText} onChange={(e) => setInputSchemaText(e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="pathMapText">Path Mapping (JSON)</Label>
                      <Textarea id="pathMapText" className="mt-1 font-mono text-sm h-20" value={pathMapText} onChange={(e) => setPathMapText(e.target.value)} placeholder='{"country": "country"}' />
                    </div>
                    <div>
                      <Label htmlFor="queryMapText">Query Mapping (JSON)</Label>
                      <Textarea id="queryMapText" className="mt-1 font-mono text-sm h-20" value={queryMapText} onChange={(e) => setQueryMapText(e.target.value)} placeholder='{"city": "city", "days": "days"}' />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="headersMapText">Headers Mapping (JSON)</Label>
                      <Textarea id="headersMapText" className="mt-1 font-mono text-sm h-20" value={headersMapText} onChange={(e) => setHeadersMapText(e.target.value)} placeholder='{"X-Api-Version": "apiVersion"}' />
                    </div>
                    <div>
                      <Label htmlFor="bodyMapText">Body Mapping (JSON)</Label>
                      <Textarea id="bodyMapText" className="mt-1 font-mono text-sm h-20" value={bodyMapText} onChange={(e) => setBodyMapText(e.target.value)} placeholder='{"text": "text", "targetLang": "target"}' />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="rawBodyKey">Raw Body Key</Label>
                    <Input id="rawBodyKey" className="mt-1 font-mono text-sm" value={rawBodyKey} onChange={(e) => setRawBodyKey(e.target.value)} placeholder="payload" />
                  </div>
                  <div>
                    <Label htmlFor="responsePick">Response Mapping (JSONPath)</Label>
                    <Input id="responsePick" className="mt-1 font-mono text-sm" value={responsePick} onChange={(e) => setResponsePick(e.target.value)} placeholder="$.forecast.daily" />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch id="toolActive" checked={toolActive} onCheckedChange={setToolActive} />
                    <Label htmlFor="toolActive">Active</Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setToolDialogOpen(false)}>Cancel</Button>
                  <Button 
                    className="bg-blue-600 hover:bg-blue-600/90" 
                    onClick={async () => { await upsertTool(); setToolDialogOpen(false); clearForm(); }}
                    disabled={(!selectedServerId && !editingToolServerId) || !toolName}
                  >
                    {editingToolName ? 'Update' : 'Save'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="space-y-4">
            {Object.entries(tools).map(([name, binding]) => {
              // 복합 키에서 실제 툴 이름과 서버 ID 추출
              const isCompositeKey = name.includes('::')
              const actualToolName = isCompositeKey ? name.split('::')[1] : name
              const toolServerId = isCompositeKey ? name.split('::')[0] : selectedServerId
              const displayServerId = binding.serverId || toolServerId
              
              return (
                <Card key={name} className="bg-white border border-gray-200">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold text-gray-900">{binding.name || actualToolName}</h3>
                            <span className={`px-2 py-1 text-xs rounded-full ${binding.active ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-600'}`}>
                              {binding.active ? 'Active' : 'Inactive'}
                            </span>
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-600">
                              {binding.method || 'GET'}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 mb-1">{binding.description || 'REST API Tool'}</p>
                          <p className="text-sm text-gray-500">Server: {displayServerId} | Path: {binding.pathTemplate || '/'}</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => testTool(actualToolName, displayServerId)} disabled={isTesting}>Test</Button>
                        <Button variant="outline" size="sm" onClick={() => editTool(actualToolName, displayServerId)}>Edit</Button>
                        <Button variant="outline" size="sm" onClick={() => deleteTool(actualToolName, displayServerId)}>Delete</Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
            {Object.entries(tools).length === 0 && (
              <Card className="bg-white border border-gray-200">
                <CardContent className="p-12 text-center">
                  <p className="text-gray-500">
                    {selectedServerId && selectedServerId !== "__all__" ? 'No tools configured for this server' : 'No tools configured'}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
      {/* Test Result Modal */}
      <Dialog open={testDialogOpen} onOpenChange={(open) => setTestDialogOpen(open)}>
        <DialogContent className="bg-white text-gray-900 border-gray-200 max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              Test Result{testingTarget ? `: ${testingTarget.serverId}/${testingTarget.toolName}` : ''}
            </DialogTitle>
          </DialogHeader>
          <div
            ref={logRef}
            className="h-72 overflow-auto bg-gray-50 border border-gray-200 rounded p-3 font-mono text-xs text-gray-800 whitespace-pre-wrap"
          >
            {testLog.length === 0 ? (
              <div className="text-gray-400">No logs</div>
            ) : (
              testLog.map((line, idx) => <div key={idx}>{line}</div>)
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTestDialogOpen(false)}>
              Close
            </Button>
            <Button onClick={() => setTestLog([])} disabled={isTesting}>
              Clear
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default App
