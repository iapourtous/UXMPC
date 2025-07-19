import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});


// Services API
export const servicesApi = {
  list: (activeOnly = false) => api.get('/services', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/services/${id}`),
  create: (data) => api.post('/services/', data),
  update: (id, data) => api.put(`/services/${id}`, data),
  delete: (id) => api.delete(`/services/${id}`),
  activate: (id) => api.post(`/services/${id}/activate`),
  deactivate: (id) => api.post(`/services/${id}/deactivate`),
};

// LLM Profiles API
export const llmApi = {
  list: (activeOnly = false) => api.get('/llms', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/llms/${id}`),
  create: (data) => api.post('/llms/', data),
  update: (id, data) => api.put(`/llms/${id}`, data),
  delete: (id) => api.delete(`/llms/${id}`),
};

// Documentation API
export const docsApi = {
  getMarkdown: () => api.get('/docs', { responseType: 'text' }),
};

// Agents API
export const agentsApi = {
  list: (activeOnly = false) => api.get('/agents', { params: { active_only: activeOnly } }),
  get: (id) => api.get(`/agents/${id}`),
  create: (data) => api.post('/agents/', data),
  update: (id, data) => api.put(`/agents/${id}`, data),
  delete: (id) => api.delete(`/agents/${id}`),
  activate: (id) => api.post(`/agents/${id}/activate`),
  deactivate: (id) => api.post(`/agents/${id}/deactivate`),
  execute: (id, data) => api.post(`/agents/${id}/execute`, data),
  validate: (id) => api.get(`/agents/${id}/validate`),
};

// Agent Memory API
export const agentMemoryApi = {
  list: (agentId, params = {}) => api.get(`/agents/${agentId}/memory`, { params }),
  search: (agentId, query, k = 5) => api.post(`/agents/${agentId}/memory/search`, { query, k }),
  get: (agentId, memoryId) => api.get(`/agents/${agentId}/memory/${memoryId}`),
  delete: (agentId, memoryId) => api.delete(`/agents/${agentId}/memory/${memoryId}`),
  clear: (agentId) => api.delete(`/agents/${agentId}/memory`),
  stats: (agentId) => api.get(`/agents/${agentId}/memory/summary`),
};

// Feedback API
export const feedbackApi = {
  create: (data) => api.post('/feedback/', data),
  list: (params = {}) => api.get('/feedback/', { params }),
  get: (id) => api.get(`/feedback/${id}`),
  getStats: () => api.get('/feedback/stats/overview'),
  getAgentStats: () => api.get('/feedback/stats/by-agent'),
};

export default api;