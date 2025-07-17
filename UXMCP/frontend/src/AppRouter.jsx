import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from 'antd';
import AppHeader from './components/AppHeader';
import AgentList from './components/AgentList';
import AgentForm from './components/AgentForm';
import AgentTest from './components/AgentTest';
import AgentMemory from './components/AgentMemory';
import LogsView from './components/LogsView';

// New Ant Design components
import ServiceListAntd from './components/ServiceListAntd';
import ServiceFormAntd from './components/ServiceFormAntd';
import LLMProfileListAntd from './components/LLMProfileListAntd';
import LLMProfileFormAntd from './components/LLMProfileFormAntd';
import ChatAntd from './components/ChatAntd';
import AgentServiceCreator from './components/AgentServiceCreator';
import MetaAgentCreator from './components/MetaAgentCreator';
import MetaChat from './components/MetaChat';

const { Content } = Layout;

function AppRouter() {
  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <AppHeader />
        <Content style={{ padding: '0', background: '#f0f2f5' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/agents" replace />} />
            
            {/* Agents Routes (new Ant Design components) */}
            <Route path="/agents" element={<AgentList />} />
            <Route path="/agents/new" element={<AgentForm />} />
            <Route path="/agents/:id/edit" element={<AgentForm />} />
            <Route path="/agents/:id/test" element={<AgentTest />} />
            <Route path="/agents/:agentId/memory" element={<AgentMemory />} />
            <Route path="/agents/create-meta" element={<MetaAgentCreator />} />
            
            {/* Logs Route */}
            <Route path="/logs" element={<LogsView />} />
            
            {/* Services Routes */}
            <Route path="/services" element={<ServiceListAntd />} />
            <Route path="/services/new" element={<ServiceFormAntd />} />
            <Route path="/services/:id/edit" element={<ServiceFormAntd />} />
            <Route path="/services/create-ai" element={<AgentServiceCreator />} />
            
            {/* LLM Profiles Routes */}
            <Route path="/llms" element={<LLMProfileListAntd />} />
            <Route path="/llms/new" element={<LLMProfileFormAntd />} />
            <Route path="/llms/:id/edit" element={<LLMProfileFormAntd />} />
            
            {/* Chat Routes */}
            <Route path="/chat" element={<ChatAntd />} />
            <Route path="/meta-chat" element={<MetaChat />} />
            
            {/* 404 Route */}
            <Route path="*" element={<Navigate to="/agents" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Router>
  );
}

export default AppRouter;