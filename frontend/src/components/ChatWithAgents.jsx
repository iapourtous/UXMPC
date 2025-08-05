import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentsApi, conversationsApi, demosApi } from '../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Select, Button, Input, Drawer, List, Typography, Popconfirm, message, Modal, Tooltip, Tag } from 'antd';
import { SendOutlined, ClearOutlined, HistoryOutlined, DeleteOutlined, PlusOutlined, SaveOutlined, EyeOutlined, ExperimentOutlined, CompressOutlined, BugOutlined } from '@ant-design/icons';
import axios from 'axios';

const { TextArea } = Input;
const { Title, Text } = Typography;

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function ChatWithAgents() {
  const [selectedAgent, setSelectedAgent] = useState('');
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [conversationTitle, setConversationTitle] = useState('');
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewContent, setPreviewContent] = useState('');
  const [demoModalOpen, setDemoModalOpen] = useState(false);
  const [demoTitle, setDemoTitle] = useState('');
  const [demoDescription, setDemoDescription] = useState('');
  const [demoHtmlContent, setDemoHtmlContent] = useState('');
  const [globalSettings, setGlobalSettings] = useState(null);
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const [debugPromptData, setDebugPromptData] = useState(null);
  const [debugUserMessage, setDebugUserMessage] = useState('');
  const messagesEndRef = useRef(null);
  const queryClient = useQueryClient();
  
  // Fetch agents list
  const { data: agentsResponse, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents', true],
    queryFn: () => agentsApi.list(true),
  });
  
  const agents = agentsResponse?.data || [];
  
  // Fetch conversation summaries
  const { data: conversationSummaries, refetch: refetchSummaries } = useQuery({
    queryKey: ['conversation-summaries'],
    queryFn: () => conversationsApi.getSummaries({ limit: 20 }),
  });
  
  // Load conversation
  const loadConversationMutation = useMutation({
    mutationFn: async (conversationId) => {
      const response = await conversationsApi.get(conversationId);
      return response.data;
    },
    onSuccess: (conversation) => {
      setCurrentConversationId(conversation._id);
      // Convert messages to display format
      const displayMessages = conversation.messages.map(msg => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
        tool_calls: msg.tool_calls,
        agent_id: msg.agent_id
      }));
      console.log('LOADING conversation with', displayMessages.length, 'messages');
      setMessages(displayMessages);
      message.success('Conversation loaded');
      
      // Update window title with conversation title
      if (conversation.title) {
        document.title = `Chat - ${conversation.title}`;
      }
    },
    onError: () => {
      message.error('Failed to load conversation');
    }
  });
  
  // Create new conversation
  const createConversationMutation = useMutation({
    mutationFn: async () => {
      const response = await conversationsApi.create({
        title: `New Chat - ${new Date().toLocaleString()}`,
        messages: []
      });
      return response.data;
    },
    onSuccess: (conversation) => {
      setCurrentConversationId(conversation._id);
      setMessages([]);
      refetchSummaries();
      message.success('New conversation created');
    },
    onError: () => {
      message.error('Failed to create conversation');
    }
  });
  
  // Delete conversation
  const deleteConversationMutation = useMutation({
    mutationFn: async (conversationId) => {
      await conversationsApi.delete(conversationId);
      return conversationId;
    },
    onSuccess: (deletedId) => {
      if (currentConversationId === deletedId) {
        setCurrentConversationId(null);
        setMessages([]);
      }
      refetchSummaries();
      message.success('Conversation deleted');
    },
    onError: () => {
      message.error('Failed to delete conversation');
    }
  });
  
  // Save conversation with custom title
  const saveConversationMutation = useMutation({
    mutationFn: async (title) => {
      console.log('SAVING CONVERSATION with', messages.length, 'messages');
      console.log('Messages being saved:', messages.map(m => `${m.role}: ${m.content.substring(0, 50)}...`));
      
      const messagesToSave = messages.map(msg => ({
        role: msg.role,
        content: msg.content,
        agent_id: msg.agent_id,
        tool_calls: msg.tool_calls || [],
        metadata: msg.metadata || {}
      }));
      
      if (currentConversationId) {
        // Update existing conversation - FORCE overwrite with current messages
        const response = await conversationsApi.update(currentConversationId, { 
          title,
          messages: messagesToSave
        });
        console.log('UPDATED conversation with', messagesToSave.length, 'messages');
        return response.data;
      } else {
        // Create new conversation
        const response = await conversationsApi.create({
          title,
          messages: messagesToSave
        });
        console.log('CREATED conversation with', messagesToSave.length, 'messages');
        return response.data;
      }
    },
    onSuccess: (conversation) => {
      setCurrentConversationId(conversation._id);
      refetchSummaries();
      setSaveModalOpen(false);
      setConversationTitle('');
      message.success('Conversation saved successfully');
      // DO NOT reload messages - keep the current state as-is
    },
    onError: () => {
      message.error('Failed to save conversation');
    }
  });
  
  // Save demo mutation
  const saveDemoMutation = useMutation({
    mutationFn: async ({ title, description, htmlContent }) => {
      const response = await demosApi.create({
        name: title.toLowerCase().replace(/\s+/g, '-'),
        query: title, // Using title as the query for now
        description,
        html_content: htmlContent,
        session_id: currentConversationId || 'manual-' + Date.now(), // Use conversation ID or generate one
        instructions: null,
        enhanced_message: null,
        auto_instruct: null,
        agent_used: selectedAgent ? agents.find(a => a.id === selectedAgent)?.name : null,
        agent_details: selectedAgent ? { agent_id: selectedAgent } : null
      });
      return response.data;
    },
    onSuccess: () => {
      message.success('Demo saved successfully!');
      setDemoModalOpen(false);
      setDemoTitle('');
      setDemoDescription('');
      setDemoHtmlContent('');
    },
    onError: (error) => {
      console.error('Save demo error:', error);
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || 'Unknown error';
      message.error('Failed to save demo: ' + errorMsg);
    }
  });
  
  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: async ({ agentId, message, conversationId }) => {
      // Convert current messages to conversation history format
      const conversationHistory = messages.map(msg => ({
        role: msg.role === 'error' ? 'assistant' : msg.role, // Convert error to assistant for context
        content: msg.content
      }));
      
      const response = await agentsApi.execute(agentId, {
        input: message,
        conversation_id: conversationId,
        conversation_history: conversationHistory, // Pass current chat history
        save_conversation: false, // Disable auto-save to prevent overriding local changes
        execution_options: {
          timeout: 180000 // 3 minutes
        }
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        // Update current conversation ID if it changed
        if (data.conversation_id && data.conversation_id !== currentConversationId) {
          setCurrentConversationId(data.conversation_id);
          refetchSummaries();
        }
        
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.output,
          tool_calls: data.tool_calls,
          agent_id: selectedAgent
        }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'error',
          content: `Error: ${data.error}${data.detail ? '\n' + data.detail : ''}`
        }]);
      }
    },
    onError: (error) => {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Failed to send message: ${error.message}`
      }]);
    }
  });
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  // Fetch global settings
  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API_URL}/settings`);
      setGlobalSettings(response.data);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    }
  };

  // Check if compaction would be active
  const isCompactionActive = () => {
    if (!globalSettings?.compaction_settings?.enabled) return false;
    if (!globalSettings?.summary_llm_profile) return false;
    if (messages.length <= globalSettings.compaction_settings.message_threshold) return false;
    return true;
  };

  // Auto-load latest conversation when component mounts
  useEffect(() => {
    fetchSettings();
    
    if (!currentConversationId) {
      conversationsApi.getLatestConversation()
        .then(response => {
          if (response.data) {
            loadConversationMutation.mutate(response.data._id);
          }
        })
        .catch(() => {
          // No existing conversation, that's ok
        });
    }
  }, []);
  
  const handleSendMessage = async (e) => {
    e.preventDefault();
    
    if (!selectedAgent) {
      message.warning('Please select an agent first');
      return;
    }
    
    if (!inputMessage.trim()) return;
    
    // Add user message to chat
    const userMessage = { role: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    
    // Send message to agent
    sendMessageMutation.mutate({
      agentId: selectedAgent,
      message: inputMessage,
      conversationId: currentConversationId
    });
  };
  
  const handleClearChat = () => {
    createConversationMutation.mutate();
  };
  
  const handleDeleteMessage = (index) => {
    setMessages(prev => {
      const newMessages = prev.filter((_, i) => i !== index);
      console.log('Messages after deletion:', newMessages.length, 'messages');
      return newMessages;
    });
  };
  
  const handleAgentChange = (value) => {
    setSelectedAgent(value);
  };
  
  const handleSaveConversation = () => {
    if (messages.length === 0) {
      message.warning('No messages to save');
      return;
    }
    setSaveModalOpen(true);
  };
  
  const handleConfirmSave = () => {
    if (!conversationTitle.trim()) {
      message.warning('Please enter a title for the conversation');
      return;
    }
    saveConversationMutation.mutate(conversationTitle);
  };
  
  // Detect HTML content in message
  const detectHTMLContent = (content) => {
    if (!content || typeof content !== 'string') return null;
    
    // Check for complete HTML document
    if (content.includes('<!DOCTYPE html') || content.includes('<html')) {
      // Extract HTML from markdown code blocks if present
      const htmlBlockMatch = content.match(/```html\n([\s\S]*?)```/);
      if (htmlBlockMatch) {
        return htmlBlockMatch[1];
      }
      
      // Check if the entire content is HTML
      const htmlMatch = content.match(/<!DOCTYPE html[\s\S]*<\/html>|<html[\s\S]*<\/html>/i);
      if (htmlMatch) {
        return htmlMatch[0];
      }
    }
    
    // Check for HTML snippets in code blocks
    const codeBlockMatch = content.match(/```(?:html)?\n([\s\S]*?)```/);
    if (codeBlockMatch) {
      const codeContent = codeBlockMatch[1];
      // Check if it contains substantial HTML (not just a single tag)
      const htmlTags = codeContent.match(/<[^>]+>/g);
      if (htmlTags && htmlTags.length > 3 && 
          (codeContent.includes('<body') || codeContent.includes('<div') || codeContent.includes('<section'))) {
        // Wrap snippet in basic HTML structure if needed
        if (!codeContent.includes('<html')) {
          return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: Arial, sans-serif; padding: 20px; }
  </style>
</head>
<body>
  ${codeContent}
</body>
</html>`;
        }
        return codeContent;
      }
    }
    
    return null;
  };
  
  const handlePreviewHTML = (htmlContent) => {
    setPreviewContent(htmlContent);
    setPreviewModalOpen(true);
  };
  
  const handleSaveAsDemo = (htmlContent) => {
    setDemoHtmlContent(htmlContent);
    setDemoModalOpen(true);
  };
  
  const handleConfirmSaveDemo = () => {
    if (!demoTitle.trim()) {
      message.warning('Please enter a title for the demo');
      return;
    }
    if (!demoDescription.trim()) {
      message.warning('Please enter a description for the demo');
      return;
    }
    saveDemoMutation.mutate({
      title: demoTitle,
      description: demoDescription,
      htmlContent: demoHtmlContent
    });
  };

  // Debug prompt function
  const handleDebugPrompt = async (userMessage) => {
    if (!selectedAgent) {
      message.warning('Please select an agent first');
      return;
    }

    try {
      setDebugUserMessage(userMessage);
      
      // Convert current messages to conversation history format
      const conversationHistory = messages.map(msg => ({
        role: msg.role === 'error' ? 'assistant' : msg.role,
        content: msg.content
      }));

      const response = await axios.post(`${API_URL}/agents/${selectedAgent}/debug-prompt`, {
        input: userMessage,
        conversation_id: currentConversationId,
        conversation_history: conversationHistory,
        save_conversation: false
      });

      setDebugPromptData(response.data);
      setDebugModalOpen(true);
    } catch (error) {
      console.error('Debug prompt error:', error);
      message.error('Failed to debug prompt: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  // Filter agents that have text input/output schemas
  const textAgents = agents.filter(agent => {
    const hasTextInput = agent.input_schema === 'text' || 
                        (typeof agent.input_schema === 'object' && agent.input_schema.type === 'string');
    const hasTextOutput = agent.output_schema === 'text' || 
                         (typeof agent.output_schema === 'object' && agent.output_schema.type === 'string');
    return hasTextInput && hasTextOutput && agent.active;
  });
  
  const currentAgent = textAgents.find(a => a.id === selectedAgent);
  
  return (
    <div className="flex flex-col h-full">
      {/* Header with Agent selector and controls */}
      <div className="bg-white shadow-sm p-4 border-b">
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">Agent:</span>
            <Select
              value={selectedAgent}
              onChange={handleAgentChange}
              className="w-64"
              placeholder="Select an agent..."
              loading={agentsLoading}
              showSearch
              optionFilterProp="children"
            >
              {textAgents.map(agent => (
                <Select.Option key={agent.id} value={agent.id}>
                  {agent.name}
                </Select.Option>
              ))}
            </Select>
          </label>
          
          <div className="ml-auto flex gap-2">
            <Button
              icon={<SaveOutlined />}
              onClick={handleSaveConversation}
              disabled={messages.length === 0}
            >
              Save
            </Button>
            <Button
              icon={<HistoryOutlined />}
              onClick={() => setHistoryDrawerOpen(true)}
            >
              History
            </Button>
            <Button
              icon={<PlusOutlined />}
              onClick={handleClearChat}
              disabled={!selectedAgent}
            >
              New Chat
            </Button>
          </div>
        </div>
        
        {currentAgent && (
          <div className="mt-2">
            <p className="text-xs text-gray-500">{currentAgent.description}</p>
            {currentAgent.backstory && (
              <p className="text-xs text-gray-400 mt-1 italic">
                {currentAgent.backstory.substring(0, 100)}...
              </p>
            )}
          </div>
        )}
        
        {currentConversationId && (
          <div className="mt-2 space-y-1">
            <Text type="secondary" className="text-xs block">
              <SaveOutlined className="mr-1" />
              Manual save only - use Save button to preserve conversation
            </Text>
            {isCompactionActive() && (
              <Tooltip title={`Messages will be compacted after ${globalSettings.compaction_settings.message_threshold} messages. Currently at ${messages.length} messages.`}>
                <Tag color="blue" icon={<CompressOutlined />} className="text-xs">
                  Compaction Active
                </Tag>
              </Tooltip>
            )}
            {globalSettings?.user_context && (
              <Tooltip title="User context is being provided to the agent">
                <Tag color="green" className="text-xs">
                  User Context Active
                </Tag>
              </Tooltip>
            )}
          </div>
        )}
      </div>
      
      {/* Messages container */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-gradient-to-br from-gray-50 via-blue-50/30 to-indigo-50/20">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-2xl flex items-center justify-center">
              <span className="text-2xl">💬</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-700 mb-2">Ready to chat!</h3>
            <p className="text-gray-500 max-w-md mx-auto leading-relaxed">
              {currentAgent ? (
                <>Start a conversation with <span className="font-medium text-indigo-600">{currentAgent.name}</span> by typing your message below.</>
              ) : (
                'Select an agent from the dropdown above to begin your conversation.'
              )}
            </p>
          </div>
        )}
        
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} group`}
          >
            <div
              className={`max-w-5xl rounded-2xl px-6 py-4 relative shadow-sm hover:shadow-md transition-all duration-200 ${
                message.role === 'user'
                  ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-blue-200/50'
                  : message.role === 'assistant'
                  ? 'bg-white/90 backdrop-blur-sm border border-gray-100 shadow-gray-200/50'
                  : 'bg-red-50/90 backdrop-blur-sm border border-red-200 text-red-700 shadow-red-200/50'
              }`}
            >
              {/* Delete button */}
              <button
                onClick={() => handleDeleteMessage(index)}
                className="absolute -top-2 -right-2 w-7 h-7 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-200 bg-red-500 hover:bg-red-600 text-white shadow-lg hover:shadow-xl transform hover:scale-110"
                title="Delete message"
              >
                <span className="text-sm font-medium">×</span>
              </button>
              <div className="flex items-center gap-2 mb-3">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  message.role === 'user' 
                    ? 'bg-white/20 text-white' 
                    : message.role === 'assistant'
                    ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white'
                    : 'bg-red-500 text-white'
                }`}>
                  {message.role === 'user' ? 'U' : 
                   message.role === 'assistant' ? '🤖' : '⚠'}
                </div>
                <div className="flex flex-col">
                  <div className={`text-sm font-medium ${message.role === 'user' ? 'text-white/90' : 'text-gray-700'}`}>
                    {message.role === 'user' ? 'You' : 
                     message.role === 'assistant' ? (
                       agents.find(a => a.id === message.agent_id)?.name || 'Agent'
                     ) : 'Error'}
                  </div>
                  {message.timestamp && (
                    <div className={`text-xs ${message.role === 'user' ? 'text-white/70' : 'text-gray-500'}`}>
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </div>
                  )}
                </div>
              </div>
              <div className="message-content">
                {message.role === 'assistant' ? (
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    className="prose prose-base max-w-none prose-gray prose-headings:text-gray-800 prose-p:text-gray-700 prose-p:leading-relaxed"
                    components={{
                      pre: ({node, ...props}) => (
                        <pre className="bg-gray-50 border rounded-xl p-4 overflow-x-auto shadow-inner" {...props} />
                      ),
                      code: ({node, inline, ...props}) => (
                        inline ? 
                          <code className="bg-gray-100 px-2 py-1 rounded-md text-sm font-mono" {...props} /> :
                          <code className="text-sm" {...props} />
                      ),
                      a: ({node, ...props}) => (
                        <a className="text-blue-600 hover:text-blue-700 underline decoration-2 underline-offset-2" target="_blank" rel="noopener noreferrer" {...props} />
                      ),
                      ul: ({node, ...props}) => (
                        <ul className="list-disc list-inside space-y-1" {...props} />
                      ),
                      ol: ({node, ...props}) => (
                        <ol className="list-decimal list-inside space-y-1" {...props} />
                      ),
                      h1: ({node, ...props}) => (
                        <h1 className="text-xl font-bold text-gray-800 mb-3 mt-4" {...props} />
                      ),
                      h2: ({node, ...props}) => (
                        <h2 className="text-lg font-semibold text-gray-800 mb-2 mt-3" {...props} />
                      ),
                      h3: ({node, ...props}) => (
                        <h3 className="text-base font-medium text-gray-800 mb-2 mt-2" {...props} />
                      ),
                      blockquote: ({node, ...props}) => (
                        <blockquote className="border-l-4 border-indigo-200 pl-4 py-2 bg-indigo-50/50 rounded-r-lg" {...props} />
                      )
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  <div className="whitespace-pre-wrap break-words text-base leading-relaxed">
                    {message.content}
                  </div>
                )}
              </div>
              {message.tool_calls && message.tool_calls.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-gradient-to-r from-green-400 to-blue-500 flex items-center justify-center">
                      <span className="text-white text-xs">🔧</span>
                    </div>
                    <span className="text-xs text-gray-600 font-medium">
                      Used {message.tool_calls.length} tool{message.tool_calls.length > 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              )}
              {/* HTML Preview and Save as Demo Buttons */}
              {(() => {
                const htmlContent = detectHTMLContent(message.content);
                if (htmlContent && message.role === 'assistant') {
                  return (
                    <div className="mt-3 pt-3 border-t border-gray-200 flex gap-2">
                      <Button
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => handlePreviewHTML(htmlContent)}
                        className="flex items-center gap-1"
                      >
                        Preview HTML
                      </Button>
                      <Button
                        size="small"
                        icon={<ExperimentOutlined />}
                        onClick={() => handleSaveAsDemo(htmlContent)}
                        className="flex items-center gap-1"
                        type="primary"
                        ghost
                      >
                        Save as Demo
                      </Button>
                    </div>
                  );
                }
                return null;
              })()}
            </div>
          </div>
        ))}
        
        {sendMessageMutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-white/90 backdrop-blur-sm border border-gray-100 rounded-2xl px-6 py-4 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                  <span className="text-white text-xs">🤖</span>
                </div>
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
                <span className="text-sm text-gray-500 font-medium">Agent is thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input form */}
      <form onSubmit={handleSendMessage} className="p-6 bg-white/80 backdrop-blur-sm border-t border-gray-100">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <TextArea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={selectedAgent ? "💬 Type your message here..." : "👋 Select an agent first to start chatting..."}
              disabled={!selectedAgent || sendMessageMutation.isPending}
              autoSize={{ minRows: 1, maxRows: 4 }}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(e);
                }
              }}
              className="rounded-xl border-gray-200 shadow-sm hover:border-blue-300 focus:border-blue-500 transition-colors duration-200"
              style={{
                resize: 'none',
                fontSize: '16px',
                lineHeight: '1.5'
              }}
            />
            <div className="text-xs text-gray-400 mt-1 ml-3">
              Press Enter to send • Shift+Enter for new line
            </div>
          </div>
          <Button
            icon={<BugOutlined />}
            onClick={() => handleDebugPrompt(inputMessage)}
            disabled={!selectedAgent || !inputMessage.trim()}
            className="h-12 px-4 rounded-xl bg-orange-500 hover:bg-orange-600 border-0 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 text-white"
            size="large"
            title="Debug this prompt"
          >
            Debug
          </Button>
          <Button
            type="primary"
            htmlType="submit"
            icon={<SendOutlined />}
            disabled={!selectedAgent || !inputMessage.trim() || sendMessageMutation.isPending}
            loading={sendMessageMutation.isPending}
            className="h-12 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 border-0 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200"
            size="large"
          >
            Send
          </Button>
        </div>
      </form>
      
      {/* Save Conversation Modal */}
      <Modal
        title="Save Conversation"
        open={saveModalOpen}
        onOk={handleConfirmSave}
        onCancel={() => {
          setSaveModalOpen(false);
          setConversationTitle('');
        }}
        confirmLoading={saveConversationMutation.isPending}
      >
        <Input
          placeholder="Enter a title for this conversation"
          value={conversationTitle}
          onChange={(e) => setConversationTitle(e.target.value)}
          onPressEnter={handleConfirmSave}
          autoFocus
        />
      </Modal>
      
      {/* Conversation History Drawer */}
      <Drawer
        title="Conversation History"
        placement="right"
        onClose={() => setHistoryDrawerOpen(false)}
        open={historyDrawerOpen}
        width={500}
      >
        <div className="mb-4">
          <Text type="secondary">
            Click on a conversation to load it. Your current conversation is highlighted in blue.
          </Text>
        </div>
        <List
          dataSource={conversationSummaries?.data || []}
          loading={!conversationSummaries}
          renderItem={(conversation) => (
            <List.Item
              actions={[
                <Button
                  type="link"
                  onClick={() => {
                    loadConversationMutation.mutate(conversation._id);
                    setHistoryDrawerOpen(false);
                  }}
                  disabled={conversation._id === currentConversationId}
                >
                  {conversation._id === currentConversationId ? 'Current' : 'Load'}
                </Button>,
                <Popconfirm
                  title="Delete this conversation?"
                  onConfirm={() => deleteConversationMutation.mutate(conversation._id)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Button type="link" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ]}
              className={conversation._id === currentConversationId ? 'bg-blue-50 border-l-4 border-blue-500' : 'hover:bg-gray-50'}
            >
              <List.Item.Meta
                title={conversation.title || 'Untitled'}
                description={
                  <div>
                    <Text type="secondary" className="text-xs">
                      {conversation.message_count} messages
                    </Text>
                    {conversation.agents_used && conversation.agents_used.length > 0 && (
                      <>
                        <br />
                        <Text type="secondary" className="text-xs">
                          Agents: {conversation.agents_used.map(agentId => 
                            agents.find(a => a.id === agentId)?.name || agentId
                          ).join(', ')}
                        </Text>
                      </>
                    )}
                    <br />
                    <Text type="secondary" className="text-xs">
                      {new Date(conversation.last_activity).toLocaleString()}
                    </Text>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Drawer>
      
      {/* HTML Preview Modal */}
      <Modal
        title="HTML Preview"
        open={previewModalOpen}
        onCancel={() => {
          setPreviewModalOpen(false);
          setPreviewContent('');
        }}
        footer={[
          <Button key="close" onClick={() => {
            setPreviewModalOpen(false);
            setPreviewContent('');
          }}>
            Close
          </Button>
        ]}
        width="90%"
        style={{ top: 20 }}
        bodyStyle={{ height: 'calc(80vh - 108px)', padding: 0 }}
      >
        <div style={{ height: '100%', width: '100%' }}>
          <iframe
            srcDoc={previewContent}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              backgroundColor: '#fff'
            }}
            sandbox="allow-scripts allow-same-origin"
            title="HTML Preview"
          />
        </div>
      </Modal>
      
      {/* Save as Demo Modal */}
      <Modal
        title="Save as Demo"
        open={demoModalOpen}
        onOk={handleConfirmSaveDemo}
        onCancel={() => {
          setDemoModalOpen(false);
          setDemoTitle('');
          setDemoDescription('');
          setDemoHtmlContent('');
        }}
        confirmLoading={saveDemoMutation.isPending}
        okText="Save Demo"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Demo Title
            </label>
            <Input
              placeholder="Enter a title for this demo"
              value={demoTitle}
              onChange={(e) => setDemoTitle(e.target.value)}
              onPressEnter={() => document.getElementById('demo-description')?.focus()}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <TextArea
              id="demo-description"
              placeholder="Describe what this demo demonstrates"
              value={demoDescription}
              onChange={(e) => setDemoDescription(e.target.value)}
              rows={4}
            />
          </div>
          
          <div>
            <Text type="secondary" className="text-xs">
              This will save the HTML content as an interactive demo that can be accessed from the Demos section.
            </Text>
          </div>
        </div>
      </Modal>
      
      {/* Debug Prompt Modal */}
      <Modal
        title={`Debug Prompt - ${debugPromptData?.agent_name || 'Agent'}`}
        open={debugModalOpen}
        onCancel={() => {
          setDebugModalOpen(false);
          setDebugPromptData(null);
          setDebugUserMessage('');
        }}
        footer={[
          <Button key="close" onClick={() => {
            setDebugModalOpen(false);
            setDebugPromptData(null);
            setDebugUserMessage('');
          }}>
            Close
          </Button>
        ]}
        width="90%"
        style={{ top: 20 }}
        bodyStyle={{ height: 'calc(80vh - 108px)', padding: '20px', overflow: 'auto' }}
      >
        {debugPromptData && (
          <div className="space-y-6">
            {/* Summary */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="font-semibold mb-2">Prompt Summary</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><strong>Agent:</strong> {debugPromptData.agent_name}</div>
                <div><strong>Memory Enabled:</strong> {debugPromptData.memory_enabled ? 'Yes' : 'No'}</div>
                <div><strong>History Messages:</strong> {debugPromptData.conversation_history_count}</div>
                <div><strong>Compaction Applied:</strong> {debugPromptData.compaction_applied ? 'Yes' : 'No'}</div>
                <div><strong>Total Messages:</strong> {debugPromptData.message_breakdown.total}</div>
                <div><strong>System/User/Assistant:</strong> {debugPromptData.message_breakdown.system_messages}/{debugPromptData.message_breakdown.user_messages}/{debugPromptData.message_breakdown.assistant_messages}</div>
              </div>
            </div>

            {/* User Input */}
            <div>
              <h3 className="font-semibold mb-2">User Input</h3>
              <div className="bg-blue-50 p-3 rounded border-l-4 border-blue-500">
                <pre className="whitespace-pre-wrap text-sm">{debugUserMessage}</pre>
              </div>
            </div>

            {/* Memory Context */}
            {debugPromptData.memory_context && (
              <div>
                <h3 className="font-semibold mb-2">Memory Context</h3>
                <div className="bg-purple-50 p-3 rounded border-l-4 border-purple-500">
                  <pre className="whitespace-pre-wrap text-sm">{debugPromptData.memory_context}</pre>
                </div>
              </div>
            )}

            {/* Global Settings */}
            <div>
              <h3 className="font-semibold mb-2">Global Settings</h3>
              <div className="bg-yellow-50 p-3 rounded border-l-4 border-yellow-500">
                <div className="text-sm">
                  <div><strong>Compaction Enabled:</strong> {debugPromptData.global_settings.compaction_enabled ? 'Yes' : 'No'}</div>
                  {debugPromptData.global_settings.user_context && (
                    <div><strong>User Context:</strong> {debugPromptData.global_settings.user_context}</div>
                  )}
                </div>
              </div>
            </div>

            {/* Final Messages */}
            <div>
              <h3 className="font-semibold mb-2">Complete Prompt Messages ({debugPromptData.final_messages.length} messages)</h3>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {debugPromptData.final_messages.map((msg, index) => (
                  <div key={index} className={`p-3 rounded border-l-4 ${
                    msg.role === 'system' ? 'bg-gray-50 border-gray-500' :
                    msg.role === 'user' ? 'bg-blue-50 border-blue-500' :
                    'bg-green-50 border-green-500'
                  }`}>
                    <div className="flex justify-between items-center mb-2">
                      <strong className="text-sm uppercase tracking-wide">{msg.role}</strong>
                      <span className="text-xs text-gray-500">Message {index + 1}</span>
                    </div>
                    <pre className="whitespace-pre-wrap text-sm font-mono">{msg.content}</pre>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default ChatWithAgents;