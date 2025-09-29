import axios from 'axios';

// Use relative URLs to leverage Vite proxy configuration
// Force empty string to use relative URLs
const API_URL = '';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});


// Services API
export const servicesApi = {
  list: (activeOnly = false) => api.get('/services/', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/services/${id}`),
  create: (data) => api.post('/services/', data),
  update: (id, data) => api.put(`/services/${id}`, data),
  delete: (id) => api.delete(`/services/${id}`),
  activate: (id) => api.post(`/services/${id}/activate`),
  deactivate: (id) => api.post(`/services/${id}/deactivate`),
};

// LLM Profiles API
export const llmApi = {
  list: (activeOnly = false) => api.get('/llms/', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/llms/${id}`),
  create: (data) => api.post('/llms/', data),
  update: (id, data) => api.put(`/llms/${id}`, data),
  delete: (id) => api.delete(`/llms/${id}`),
};

// Documentation API
export const docsApi = {
  getMarkdown: () => api.get('/docs/', { responseType: 'text' }),
};

// Agents API
export const agentsApi = {
  list: (activeOnly = false) => api.get('/agents/', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/agents/${id}`),
  create: (data) => api.post('/agents/', data),
  update: (id, data) => api.put(`/agents/${id}`, data),
  delete: (id) => api.delete(`/agents/${id}`),
  activate: (id) => api.post(`/agents/${id}/activate`),
  deactivate: (id) => api.post(`/agents/${id}/deactivate`),
  execute: (id, data) => api.post(`/agents/${id}/execute`, data),
  validate: (id) => api.get(`/agents/${id}/validate`),
  convertToTool: (id) => api.post(`/agents/${id}/convert-to-tool`),
  improvePrompt: (id) => `/api/agents/${id}/improve-prompt`, // Returns SSE endpoint URL
  improveFromFeedback: (id, feedback, lastResponse, context) => {
    const params = new URLSearchParams({
      feedback,
      last_response: lastResponse,
      context: JSON.stringify(context)
    });
    return `${API_URL}/agents/${id}/improve-from-feedback?${params}`;
  }
};

// Conversations API
export const conversationsApi = {
  list: (params = {}) => api.get('/conversations/', { params }),
  get: (id) => api.get(`/conversations/${id}`),
  create: (data) => api.post('/conversations/', data),
  update: (id, data) => api.put(`/conversations/${id}`, data),
  delete: (id) => api.delete(`/conversations/${id}`),
  addMessage: (id, message) => api.post(`/conversations/${id}/messages`, message),
  clearMessages: (id) => api.post(`/conversations/${id}/clear`),
  getSummaries: (params = {}) => api.get('/conversations/summaries', { params }),
  getLatestConversation: (userId = null) => 
    api.get(`/conversations/latest`, { params: userId ? { user_id: userId } : {} }),
};

// Agent Memory API
export const agentMemoryApi = {
  list: (agentId, params = {}) => api.get(`/agents/${agentId}/memory`, { params }),
  search: (agentId, query, k = 5) => api.post(`/agents/${agentId}/memory/search`, { query, k }),
  get: (agentId, memoryId) => api.get(`/agents/${agentId}/memory/${memoryId}`),
  delete: (agentId, memoryId) => api.delete(`/agents/${agentId}/memory/${memoryId}`),
  clear: (agentId) => api.delete(`/agents/${agentId}/memory`),
  stats: (agentId) => api.get(`/agents/${agentId}/memory/summary`),
  consolidationPreview: (agentId) => api.get(`/agents/${agentId}/memory/consolidation-preview`),
  consolidate: (agentId, iterations = 5) => api.post(`/agents/${agentId}/memory/consolidate`, { iterations }),
};

// Demos API
export const demosApi = {
  create: (data) => api.post('/demos/', data),
  list: (params = {}) => api.get('/demos/', { params }),
  get: (id) => api.get(`/demos/details/${id}`),
  update: (id, data) => api.put(`/demos/${id}`, data),
  delete: (id) => api.delete(`/demos/${id}`),
};

// Documents API
export const documentsApi = {
  create: (formData) => api.post('/api/documents/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  list: (params = {}) => api.get('/api/documents/', { params }),
  get: (id) => api.get(`/api/documents/${id}`),
  update: (id, data) => api.put(`/api/documents/${id}`, data),
  delete: (id) => api.delete(`/api/documents/${id}`),
  download: (id) => api.get(`/api/documents/${id}/download`, { responseType: 'blob' }),
  search: (searchParams) => api.post('/api/documents/search', searchParams),
  extractContent: (id) => api.post(`/api/documents/${id}/extract`),
  getContent: (id) => api.get(`/api/documents/${id}/content`),
};

// Workspaces API
export const workspacesApi = {
  create: (data) => api.post('/api/workspaces/', data),
  list: (params = {}) => api.get('/api/workspaces/', { params }),
  get: (id) => api.get(`/api/workspaces/${id}`),
  getByName: (name) => api.get(`/api/workspaces/by-name/${name}`),
  update: (id, data) => api.put(`/api/workspaces/${id}`, data),
  delete: (id) => api.delete(`/api/workspaces/${id}`),
  addAgent: (workspaceId, agentId) => api.post(`/api/workspaces/${workspaceId}/agents/${agentId}`),
  removeAgent: (workspaceId, agentId) => api.delete(`/api/workspaces/${workspaceId}/agents/${agentId}`),
  getStats: (id) => api.get(`/api/workspaces/${id}/stats`),
};

// MCP Connections API
export const mcpConnectionsApi = {
  listConnections: () => api.get('/mcp-connections/').then(response => response.data),
  getConnection: (id) => api.get(`/mcp-connections/${id}`).then(response => response.data),
  createConnection: (data) => api.post('/mcp-connections/', data).then(response => response.data),
  updateConnection: (id, data) => api.put(`/mcp-connections/${id}`, data).then(response => response.data),
  deleteConnection: (id) => api.delete(`/mcp-connections/${id}`).then(response => response.data),
  
  // Connection testing and sync
  testConnection: (id) => api.post(`/mcp-connections/${id}/test`).then(response => response.data),
  syncConnection: (id) => api.post(`/mcp-connections/${id}/sync`).then(response => response.data),
  
  // Tools, resources, prompts
  getConnectionTools: (id) => api.get(`/mcp-connections/${id}/tools`).then(response => response.data),
  getConnectionResources: (id) => api.get(`/mcp-connections/${id}/resources`).then(response => response.data),
  getConnectionPrompts: (id) => api.get(`/mcp-connections/${id}/prompts`).then(response => response.data),
  
  // Tool execution
  executeTool: (connectionId, toolName, toolCall) => 
    api.post(`/mcp-connections/${connectionId}/tools/${toolName}/execute`, toolCall).then(response => response.data),
  
  // Authentication
  getAuthStatus: (id) => api.get(`/mcp-connections/${id}/auth`).then(response => response.data),
  startOAuthFlow: (id, authConfig) => api.post(`/mcp-connections/${id}/auth/oauth`, authConfig).then(response => response.data),
  handleOAuthCallback: (id, code, state) => 
    api.post(`/mcp-connections/${id}/auth/callback`, { code, state }).then(response => response.data),
  refreshToken: (id) => api.post(`/mcp-connections/${id}/auth/refresh`).then(response => response.data),
  storeApiKey: (id, apiKeyData) => api.post(`/mcp-connections/${id}/auth/api-key`, apiKeyData).then(response => response.data),
  deleteAuth: (id) => api.delete(`/mcp-connections/${id}/auth`).then(response => response.data),
  
  // Management
  getSessionsInfo: () => api.get('/mcp-connections/sessions/info').then(response => response.data),
  cleanupSessions: (maxIdleMinutes = 30) => 
    api.post('/mcp-connections/sessions/cleanup', { max_idle_minutes: maxIdleMinutes }).then(response => response.data),
};

export default api;