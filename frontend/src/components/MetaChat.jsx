import React, { useState, useEffect, useRef } from 'react';
import { Input, Select, Button, Card, Spin, message, Empty, Modal } from 'antd';
import { SendOutlined, RobotOutlined, SettingOutlined, FullscreenOutlined, FullscreenExitOutlined, CloseOutlined } from '@ant-design/icons';
import { llmApi } from '../services/api';
import './MetaChat.css';

const { Option } = Select;
const { TextArea } = Input;

const MetaChat = () => {
  const [query, setQuery] = useState('');
  const [llmProfile, setLlmProfile] = useState(null);
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [htmlContent, setHtmlContent] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [instruct, setInstruct] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentQuery, setCurrentQuery] = useState('');
  const iframeRef = useRef(null);

  useEffect(() => {
    fetchLLMProfiles();
  }, []);

  useEffect(() => {
    // Prevent arrow keys from scrolling the page when modal is open
    const handleKeyDown = (e) => {
      if (modalVisible && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
        e.preventDefault();
      }
    };

    // Add/remove body class to prevent scrolling
    if (modalVisible) {
      document.body.classList.add('modal-open');
      window.addEventListener('keydown', handleKeyDown);
    } else {
      document.body.classList.remove('modal-open');
    }

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.classList.remove('modal-open');
    };
  }, [modalVisible]);

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
    setCurrentQuery(query);
    setModalVisible(true);

    try {
      const requestBody = {
        message: query,
        llm_profile: llmProfile
      };
      
      // Add instruct field if provided
      if (instruct.trim()) {
        requestBody.instruct = `Custom Presentation Instructions:
${instruct}`;
      }
      
      const response = await fetch('http://localhost:8000/meta-chat/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
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

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const closeModal = () => {
    setModalVisible(false);
    setIsFullscreen(false);
    setHtmlContent('');
    setCurrentQuery('');
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
          
          {/* Advanced Options */}
          <div className="advanced-section">
            <button
              className="advanced-toggle"
              onClick={() => setShowAdvanced(!showAdvanced)}
              type="button"
            >
              <SettingOutlined /> Advanced options
            </button>
            
            {showAdvanced && (
              <div className="advanced-content">
                <TextArea
                  value={instruct}
                  onChange={(e) => setInstruct(e.target.value)}
                  placeholder="Enter custom presentation instructions (optional)...
Example: 'Use a dark theme with neon colors' or 'Create a minimalist design with large typography'"
                  rows={3}
                  className="instruct-textarea"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Results Section - Now shows empty state */}
      <div className="metachat-results-section">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="Ask a question to get started"
          className="empty-state"
        />
      </div>

      {/* Response Modal */}
      <Modal
        visible={modalVisible}
        onCancel={closeModal}
        width={isFullscreen ? "100vw" : "90%"}
        style={{ 
          top: isFullscreen ? 0 : 20,
          maxWidth: isFullscreen ? "100%" : "1400px"
        }}
        bodyStyle={{ 
          height: isFullscreen ? "calc(100vh - 55px)" : "80vh", 
          padding: 0,
          overflow: "hidden"
        }}
        className={`metachat-modal ${isFullscreen ? 'fullscreen' : ''}`}
        closeIcon={<CloseOutlined />}
        title={
          <div className="modal-header">
            <span className="modal-query" title={currentQuery}>
              {currentQuery.length > 100 ? currentQuery.substring(0, 100) + '...' : currentQuery}
            </span>
            <div className="modal-actions">
              <Button 
                icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
                onClick={toggleFullscreen}
                type="text"
                title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              />
            </div>
          </div>
        }
        footer={null}
      >
        {loading ? (
          <div className="modal-loading">
            <Spin size="large" tip="Processing your request..." />
          </div>
        ) : (
          htmlContent && (
            <iframe
              ref={iframeRef}
              srcDoc={htmlContent}
              className="modal-iframe"
              title="Response Visualization"
              sandbox="allow-scripts"
              onLoad={() => {
                // Focus the iframe to ensure it captures keyboard events
                if (iframeRef.current) {
                  iframeRef.current.focus();
                }
              }}
            />
          )
        )}
      </Modal>
    </div>
  );
};

export default MetaChat;