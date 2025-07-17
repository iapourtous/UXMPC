import { useState, useRef, useEffect } from 'react';
import { useLLMProfiles } from '../hooks/useLLMProfiles';
import { useMutation } from '@tanstack/react-query';
import api from '../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function Chat() {
  const [selectedProfile, setSelectedProfile] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef(null);
  
  const { data: profiles, isLoading: profilesLoading } = useLLMProfiles();
  
  const sendMessageMutation = useMutation({
    mutationFn: async ({ llmProfileId, message, conversationHistory }) => {
      const response = await api.post('/api/chat', {
        llm_profile_id: llmProfileId,
        message,
        conversation_history: conversationHistory
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message
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
  
  const handleSendMessage = async (e) => {
    e.preventDefault();
    
    if (!selectedProfile) {
      alert('Please select an LLM profile first');
      return;
    }
    
    if (!inputMessage.trim()) return;
    
    // Add user message to chat
    const userMessage = { role: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    
    // Send message to API - filter out system messages from history
    const conversationHistory = messages.filter(m => m.role !== 'system');
    sendMessageMutation.mutate({
      llmProfileId: selectedProfile,
      message: inputMessage,
      conversationHistory: conversationHistory
    });
  };
  
  const handleClearChat = () => {
    setMessages([]);
  };
  
  const activeProfiles = profiles?.filter(p => p.active && (p.mode === 'text' || p.mode === 'markdown')) || [];
  
  const currentProfile = activeProfiles.find(p => p.id === selectedProfile);
  const isMarkdownMode = currentProfile?.mode === 'markdown';
  
  // Clean markdown content by removing ```markdown wrappers
  const cleanMarkdownContent = (content) => {
    // Remove opening ```markdown or ```md
    content = content.replace(/^```(?:markdown|md)\n/i, '');
    // Remove closing ```
    content = content.replace(/\n```$/, '');
    return content;
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* Header with LLM selector */}
      <div className="bg-white shadow-sm p-4 border-b">
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">LLM Profile:</span>
            <select
              value={selectedProfile}
              onChange={(e) => setSelectedProfile(e.target.value)}
              className="border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={profilesLoading}
            >
              <option value="">Select a profile...</option>
              {activeProfiles.map(profile => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} ({profile.model})
                </option>
              ))}
            </select>
          </label>
          
          <button
            onClick={handleClearChat}
            className="ml-auto px-3 py-1.5 text-sm bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
          >
            Clear Chat
          </button>
        </div>
        
        {selectedProfile && activeProfiles.length > 0 && (
          <div className="mt-2 text-xs text-gray-500">
            {activeProfiles.find(p => p.id === selectedProfile)?.description}
          </div>
        )}
      </div>
      
      {/* Messages container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg font-medium">No messages yet</p>
            <p className="text-sm mt-1">Select an LLM profile and start chatting!</p>
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
                {message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Assistant' : 'Error'}
              </div>
              <div className="message-content">
                {message.role === 'assistant' && isMarkdownMode ? (
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
                    {cleanMarkdownContent(message.content)}
                  </ReactMarkdown>
                ) : (
                  <div className="whitespace-pre-wrap break-words">
                    {message.content}
                  </div>
                )}
              </div>
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
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder={selectedProfile ? "Type your message..." : "Select an LLM profile first..."}
            className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={!selectedProfile || sendMessageMutation.isPending}
          />
          <button
            type="submit"
            disabled={!selectedProfile || !inputMessage.trim() || sendMessageMutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}

export default Chat;