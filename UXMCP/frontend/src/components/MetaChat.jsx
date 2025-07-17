import React, { useState, useEffect, useRef } from 'react';
import { Input, Select, Button, Card, Spin, message, Empty } from 'antd';
import { SendOutlined, RobotOutlined } from '@ant-design/icons';
import { llmApi } from '../services/api';
import './MetaChat.css';

const { Option } = Select;

const MetaChat = () => {
  const [query, setQuery] = useState('');
  const [llmProfile, setLlmProfile] = useState(null);
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [htmlContent, setHtmlContent] = useState('');
  const iframeRef = useRef(null);

  useEffect(() => {
    fetchLLMProfiles();
  }, []);

  const fetchLLMProfiles = async () => {
    try {
      const response = await llmApi.list(true);
      // Filter only JSON mode profiles
      const jsonProfiles = response.data.filter(profile => profile.mode === 'json');
      setLlmProfiles(jsonProfiles);
      
      // Set default profile if available
      if (jsonProfiles.length > 0) {
        setLlmProfile(jsonProfiles[0].name);
      }
    } catch (error) {
      message.error('Failed to fetch LLM profiles');
    }
  };

  const handleSubmit = async () => {
    if (!query.trim()) {
      message.warning('Please enter a question');
      return;
    }

    if (!llmProfile) {
      message.warning('Please select an LLM profile');
      return;
    }

    setLoading(true);
    setHtmlContent('');

    try {
      const response = await fetch('http://localhost:8000/meta-chat/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: query,
          llm_profile: llmProfile
        })
      });

      const data = await response.json();

      if (data.success && data.html_response) {
        setHtmlContent(data.html_response);
      } else if (data.error) {
        message.error(data.error);
      } else {
        message.error('No visualization generated');
      }
    } catch (error) {
      message.error('Failed to process query');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="metachat-container">
      {/* Search Section */}
      <div className="metachat-search-section">
        <div className="metachat-logo">
          <RobotOutlined className="logo-icon" />
          <h1>Meta Chat</h1>
        </div>
        
        <div className="metachat-search-box">
          <Input.TextArea
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me anything..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
          />
          
          <div className="search-controls">
            <Select
              className="llm-selector"
              value={llmProfile}
              onChange={setLlmProfile}
              placeholder="Select AI Model"
              disabled={loading}
            >
              {llmProfiles.map(profile => (
                <Option key={profile.name} value={profile.name}>
                  {profile.name} ({profile.model})
                </Option>
              ))}
            </Select>
            
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSubmit}
              loading={loading}
              className="send-button"
            >
              Send
            </Button>
          </div>
        </div>
      </div>

      {/* Results Section */}
      <div className="metachat-results-section">
        {loading && (
          <div className="loading-container">
            <Spin size="large" tip="Processing your request..." />
          </div>
        )}

        {!loading && !htmlContent && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Ask a question to get started"
            className="empty-state"
          />
        )}

        {!loading && htmlContent && (
          <div className="result-container">
            <iframe
              ref={iframeRef}
              srcDoc={htmlContent}
              className="result-iframe"
              title="Response Visualization"
              sandbox="allow-scripts"
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default MetaChat;