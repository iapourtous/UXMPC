import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  Input,
  Button,
  Select,
  Space,
  List,
  Avatar,
  Typography,
  Spin,
  Empty,
  message,
  Tag,
  Row,
  Col,
  Divider
} from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  MessageOutlined,
  ClearOutlined,
  DatabaseOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { llmApi } from '../services/api';
import api from '../services/api';

const { TextArea } = Input;
const { Option } = Select;
const { Text } = Typography;

const ChatAntd = () => {
  const [selectedProfile, setSelectedProfile] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [llmProfiles, setLlmProfiles] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchLLMProfiles();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchLLMProfiles = async () => {
    try {
      const response = await llmApi.list(true); // Only active profiles
      setLlmProfiles(response.data);
      if (response.data.length > 0 && !selectedProfile) {
        setSelectedProfile(response.data[0].id);
      }
    } catch (error) {
      message.error('Failed to fetch LLM profiles');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (!inputMessage.trim() || !selectedProfile) {
      if (!selectedProfile) {
        message.warning('Please select an LLM profile');
      }
      return;
    }

    const userMessage = { role: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await api.post('/api/chat', {
        llm_profile_id: selectedProfile,
        message: inputMessage,
        conversation_history: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      });

      if (response.data.success && response.data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response.data.message,
          model: response.data.model,
          usage: response.data.usage
        }]);
      } else {
        throw new Error(response.data.error || 'Failed to get response');
      }
    } catch (error) {
      message.error(error.response?.data?.detail || error.message || 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([]);
    message.success('Chat cleared');
  };

  const selectedProfileData = llmProfiles.find(p => p.id === selectedProfile);

  const renderMessage = (msg, index) => {
    const isUser = msg.role === 'user';
    
    return (
      <List.Item
        key={index}
        style={{
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          padding: '16px 0'
        }}
      >
        <Space align="start" style={{ maxWidth: '70%' }}>
          {!isUser && (
            <Avatar
              icon={<RobotOutlined />}
              style={{ backgroundColor: '#1890ff' }}
              size="large"
            />
          )}
          <Card
            size="small"
            style={{
              backgroundColor: isUser ? '#e6f7ff' : '#f0f2f5',
              border: 'none'
            }}
          >
            {!isUser && msg.model && (
              <div style={{ marginBottom: 8 }}>
                <Tag color="blue" size="small">{msg.model}</Tag>
                {msg.usage && (
                  <Text type="secondary" style={{ fontSize: '12px', marginLeft: 8 }}>
                    {msg.usage.total_tokens} tokens
                  </Text>
                )}
              </div>
            )}
            <div className="markdown-content">
              {isUser ? (
                <Text>{msg.content}</Text>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              )}
            </div>
          </Card>
          {isUser && (
            <Avatar
              icon={<UserOutlined />}
              style={{ backgroundColor: '#52c41a' }}
              size="large"
            />
          )}
        </Space>
      </List.Item>
    );
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Card
        title={
          <Space>
            <MessageOutlined style={{ fontSize: '24px' }} />
            <span>Chat Interface</span>
          </Space>
        }
        extra={
          <Space>
            <Select
              value={selectedProfile}
              onChange={setSelectedProfile}
              style={{ width: 300 }}
              placeholder="Select LLM Profile"
              disabled={loading}
            >
              {llmProfiles.map(profile => (
                <Option key={profile.id} value={profile.id}>
                  <Space>
                    <DatabaseOutlined />
                    {profile.name}
                    <Tag color="purple" size="small">{profile.model}</Tag>
                  </Space>
                </Option>
              ))}
            </Select>
            <Button
              icon={<ClearOutlined />}
              onClick={clearChat}
              disabled={messages.length === 0}
            >
              Clear Chat
            </Button>
          </Space>
        }
        style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0 }}
      >
        <div style={{ flex: 1, overflow: 'auto', padding: '0 24px' }}>
          {messages.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="Start a conversation"
              style={{ marginTop: '20%' }}
            >
              {selectedProfileData && (
                <div style={{ marginTop: 16 }}>
                  <Text type="secondary">
                    Using: {selectedProfileData.model}
                  </Text>
                  {selectedProfileData.system_prompt && (
                    <div style={{ marginTop: 8, maxWidth: 500, margin: '8px auto' }}>
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {selectedProfileData.system_prompt}
                      </Text>
                    </div>
                  )}
                </div>
              )}
            </Empty>
          ) : (
            <List
              dataSource={messages}
              renderItem={renderMessage}
              style={{ paddingBottom: 24 }}
            />
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <Divider style={{ margin: 0 }} />
        
        <div style={{ padding: 24 }}>
          <Row gutter={16} align="bottom">
            <Col flex="auto">
              <TextArea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message... (Shift+Enter for new line)"
                autoSize={{ minRows: 1, maxRows: 6 }}
                disabled={loading || !selectedProfile}
              />
            </Col>
            <Col>
              <Button
                type="primary"
                icon={loading ? <LoadingOutlined /> : <SendOutlined />}
                onClick={handleSend}
                disabled={!inputMessage.trim() || !selectedProfile || loading}
                size="large"
              >
                Send
              </Button>
            </Col>
          </Row>
        </div>
      </Card>
      
      <style jsx>{`
        .markdown-content h1 { font-size: 1.5em; margin: 0.5em 0; }
        .markdown-content h2 { font-size: 1.3em; margin: 0.5em 0; }
        .markdown-content h3 { font-size: 1.1em; margin: 0.5em 0; }
        .markdown-content p { margin: 0.5em 0; }
        .markdown-content ul, .markdown-content ol { margin: 0.5em 0; padding-left: 1.5em; }
        .markdown-content pre { 
          background: #f5f5f5; 
          padding: 12px; 
          border-radius: 4px; 
          overflow: auto;
          margin: 0.5em 0;
        }
        .markdown-content code { 
          background: #f0f0f0; 
          padding: 2px 4px; 
          border-radius: 3px; 
          font-family: 'Consolas', 'Monaco', monospace;
        }
        .markdown-content pre code { 
          background: none; 
          padding: 0;
        }
        .markdown-content blockquote {
          border-left: 4px solid #ddd;
          margin: 0.5em 0;
          padding-left: 1em;
          color: #666;
        }
        .markdown-content table {
          border-collapse: collapse;
          margin: 0.5em 0;
        }
        .markdown-content th, .markdown-content td {
          border: 1px solid #ddd;
          padding: 8px;
        }
        .markdown-content th {
          background: #f5f5f5;
        }
      `}</style>
    </div>
  );
};

export default ChatAntd;