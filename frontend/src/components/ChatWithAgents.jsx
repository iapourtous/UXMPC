import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentsApi, conversationsApi, demosApi } from '../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Select, Button, Input, Drawer, List, Typography, Popconfirm, message, Modal } from 'antd';
import { SendOutlined, ClearOutlined, HistoryOutlined, DeleteOutlined, PlusOutlined, SaveOutlined, EyeOutlined, ExperimentOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Title, Text } = Typography;

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
      if (currentConversationId) {
        // Update existing conversation title
        const response = await conversationsApi.update(currentConversationId, { title });
        return response.data;
      } else {
        // Create new conversation with title
        const response = await conversationsApi.create({
          title,
          messages: messages.map(msg => ({
            role: msg.role,
            content: msg.content,
            agent_id: msg.agent_id,
            tool_calls: msg.tool_calls,
            metadata: msg.metadata || {}
          }))
        });
        return response.data;
      }
    },
    onSuccess: (conversation) => {
      setCurrentConversationId(conversation._id);
      refetchSummaries();
      setSaveModalOpen(false);
      setConversationTitle('');
      message.success('Conversation saved successfully');
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
      const response = await agentsApi.execute(agentId, {
        input: message,
        conversation_id: conversationId,
        save_conversation: true,
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
  
  // Auto-load latest conversation when component mounts
  useEffect(() => {
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
          <div className="mt-2">
            <Text type="secondary" className="text-xs">
              <SaveOutlined className="mr-1" />
              Conversation is being auto-saved
            </Text>
          </div>
        )}
      </div>
      
      {/* Messages container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg font-medium">No messages yet</p>
            <p className="text-sm mt-1">Start a conversation with {currentAgent?.name || 'an agent'}!</p>
          </div>
        )}
        
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : message.role === 'assistant'
                  ? 'bg-white border border-gray-200'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              <div className="text-xs font-medium mb-1 opacity-70">
                {message.role === 'user' ? 'You' : 
                 message.role === 'assistant' ? (
                   // Find agent name from agent_id in message
                   agents.find(a => a.id === message.agent_id)?.name || 'Agent'
                 ) : 'Error'}
                {message.timestamp && (
                  <span className="ml-2">
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>
              <div className="message-content">
                {message.role === 'assistant' ? (
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    className="prose prose-sm max-w-none"
                    components={{
                      pre: ({node, ...props}) => (
                        <pre className="bg-gray-100 rounded p-2 overflow-x-auto" {...props} />
                      ),
                      code: ({node, inline, ...props}) => (
                        inline ? 
                          <code className="bg-gray-100 px-1 rounded" {...props} /> :
                          <code {...props} />
                      ),
                      a: ({node, ...props}) => (
                        <a className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />
                      ),
                      ul: ({node, ...props}) => (
                        <ul className="list-disc list-inside" {...props} />
                      ),
                      ol: ({node, ...props}) => (
                        <ol className="list-decimal list-inside" {...props} />
                      )
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  <div className="whitespace-pre-wrap break-words">
                    {message.content}
                  </div>
                )}
              </div>
              {message.tool_calls && message.tool_calls.length > 0 && (
                <div className="mt-2 text-xs opacity-70">
                  Used {message.tool_calls.length} tool{message.tool_calls.length > 1 ? 's' : ''}
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
            <div className="bg-gray-200 rounded-lg px-4 py-2">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input form */}
      <form onSubmit={handleSendMessage} className="p-4 bg-white border-t">
        <div className="flex gap-2">
          <TextArea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder={selectedAgent ? "Type your message..." : "Select an agent first..."}
            disabled={!selectedAgent || sendMessageMutation.isPending}
            autoSize={{ minRows: 1, maxRows: 4 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSendMessage(e);
              }
            }}
            className="flex-1"
          />
          <Button
            type="primary"
            htmlType="submit"
            icon={<SendOutlined />}
            disabled={!selectedAgent || !inputMessage.trim() || sendMessageMutation.isPending}
            loading={sendMessageMutation.isPending}
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
    </div>
  );
}

export default ChatWithAgents;