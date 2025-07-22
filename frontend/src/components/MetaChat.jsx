import React, { useState, useEffect, useRef } from 'react';
import { Input, Select, Button, Card, Spin, message, Empty, Modal, Rate, Form } from 'antd';
import { SendOutlined, RobotOutlined, SettingOutlined, FullscreenOutlined, FullscreenExitOutlined, CloseOutlined, LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import { llmApi, feedbackApi, demosApi } from '../services/api';
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
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackModalVisible, setFeedbackModalVisible] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [sessionData, setSessionData] = useState(null);
  const [demoFormVisible, setDemoFormVisible] = useState(false);
  const [demoForm] = Form.useForm();
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
    setShowFeedback(false);

    try {
      // Step 1: Enhance the query and instructions
      message.loading('Enhancing your query...', 1);
      
      const enhanceResponse = await fetch('http://localhost:8000/meta-chat/enhance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          instructions: instruct || null,
          llm_profile: llmProfile
        })
      });

      if (!enhanceResponse.ok) {
        throw new Error('Failed to enhance query');
      }

      const enhancedData = await enhanceResponse.json();
      
      // Use enhanced values or fallback to original
      const enhancedQuery = enhancedData.enhanced_query || query;
      const enhancedInstructions = enhancedData.enhanced_instructions || instruct;
      
      // Step 2: Process the enhanced query
      message.loading('Processing request...', 0);
      
      const requestBody = {
        message: enhancedQuery,
        llm_profile: llmProfile
      };
      
      // Add enhanced instructions if available
      if (enhancedInstructions && enhancedInstructions.trim()) {
        requestBody.instruct = enhancedInstructions;
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
        // Store session data for feedback
        setSessionData({
          session_id: data.session_id,
          user_message: query,
          custom_instructions: instruct.trim() || null,
          original_request: query,
          enhanced_query: enhancedQuery,
          enhanced_instructions: enhancedInstructions,
          agent_used: data.agent_used || 'direct',
          agent_response: data.response_data,
          final_html_response: data.html_response
        });
        message.destroy(); // Remove loading message
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
    // Show feedback options after closing modal
    if (sessionData) {
      setShowFeedback(true);
    }
  };

  const handleFeedback = async (rating) => {
    if (rating === 'positive') {
      // Ask if user wants to save as demo
      Modal.confirm({
        title: 'Save as demo?',
        content: 'Would you like to save this response as an interactive demo?',
        onOk: () => {
          // Show demo form
          setDemoFormVisible(true);
        },
        onCancel: async () => {
          // Just submit positive feedback
          try {
            await feedbackApi.create({
              ...sessionData,
              rating: 'positive',
              feedback_text: null
            });
            message.success('Thank you for your feedback!');
          } catch (error) {
            console.error('Failed to submit feedback:', error);
          }
          resetForNewQuery();
        }
      });
    } else {
      // Show feedback form for negative rating
      setFeedbackModalVisible(true);
    }
  };

  const submitNegativeFeedback = async () => {
    try {
      await feedbackApi.create({
        ...sessionData,
        rating: 'negative',
        feedback_text: feedbackText
      });
      message.success('Thank you for your feedback!');
      setFeedbackModalVisible(false);
      resetForNewQuery();
    } catch (error) {
      message.error('Failed to submit feedback');
    }
  };

  const resetForNewQuery = () => {
    setShowFeedback(false);
    setHtmlContent('');
    setCurrentQuery('');
    setQuery('');
    setInstruct('');
    setSessionData(null);
    setFeedbackText('');
    demoForm.resetFields();
  };

  const handleSaveDemo = async () => {
    try {
      const values = await demoForm.validateFields();
      
      // Ensure we have all required data
      if (!htmlContent) {
        message.error('No HTML content to save');
        return;
      }
      
      if (!sessionData) {
        message.error('Session data not available');
        return;
      }
      
      // Create demo with the HTML content and metadata
      const demoData = {
        name: values.name.toLowerCase().replace(/\s+/g, '-'),
        query: currentQuery,
        instructions: sessionData.custom_instructions || null,
        description: values.description,
        html_content: htmlContent,
        session_id: sessionData.session_id || 'unknown'
      };
      
      console.log('Saving demo with data:', demoData);
      
      await demosApi.create(demoData);
      
      // Also submit positive feedback
      await feedbackApi.create({
        ...sessionData,
        rating: 'positive',
        feedback_text: null
      });
      
      message.success('Demo saved successfully!');
      setDemoFormVisible(false);
      resetForNewQuery();
    } catch (error) {
      console.error('Failed to save demo:', error);
      console.error('Error response:', error.response?.data);
      if (error.response?.data?.detail) {
        message.error(`Failed to save demo: ${error.response.data.detail}`);
      } else {
        message.error('Failed to save demo');
      }
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

      {/* Results Section - Now shows empty state or feedback */}
      <div className="metachat-results-section">
        {showFeedback ? (
          <div className="feedback-section">
            <h3>How was the response?</h3>
            <div className="feedback-buttons">
              <Button
                icon={<LikeOutlined />}
                size="large"
                type="primary"
                onClick={() => handleFeedback('positive')}
                className="feedback-btn positive"
              >
                Good
              </Button>
              <Button
                icon={<DislikeOutlined />}
                size="large"
                onClick={() => handleFeedback('negative')}
                className="feedback-btn negative"
              >
                Not Good
              </Button>
            </div>
          </div>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Ask a question to get started"
            className="empty-state"
          />
        )}
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

      {/* Feedback Modal */}
      <Modal
        visible={feedbackModalVisible}
        onCancel={() => setFeedbackModalVisible(false)}
        onOk={submitNegativeFeedback}
        title="Provide Feedback"
        okText="Submit"
        cancelText="Cancel"
        width={500}
      >
        <div className="feedback-form">
          <p>What could have been better about the response?</p>
          <Input.TextArea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="Please describe what was wrong or what you expected..."
            rows={4}
            autoFocus
          />
        </div>
      </Modal>

      {/* Demo Save Modal */}
      <Modal
        title="Save as Interactive Demo"
        visible={demoFormVisible}
        onOk={handleSaveDemo}
        onCancel={() => setDemoFormVisible(false)}
        okText="Save Demo"
        width={500}
      >
        <Form
          form={demoForm}
          layout="vertical"
          initialValues={{
            name: '',
            description: ''
          }}
        >
          <Form.Item
            label="Demo Name (URL-friendly)"
            name="name"
            rules={[
              { required: true, message: 'Please enter a name' },
              { pattern: /^[a-zA-Z0-9-\s]+$/, message: 'Only letters, numbers, hyphens and spaces allowed' },
              { min: 3, message: 'Name must be at least 3 characters' },
              { max: 50, message: 'Name must be less than 50 characters' }
            ]}
          >
            <Input placeholder="e.g., snake-game" />
          </Form.Item>
          
          <Form.Item
            label="Description"
            name="description"
            rules={[
              { required: true, message: 'Please enter a description' },
              { max: 200, message: 'Description must be less than 200 characters' }
            ]}
          >
            <TextArea 
              placeholder="Brief description of what this demo does..."
              rows={3}
            />
          </Form.Item>
          
          <div style={{ marginTop: 16, color: '#666' }}>
            <small>The demo will be accessible at: http://localhost:8000/demos/{demoForm.getFieldValue('name')?.toLowerCase().replace(/\s+/g, '-') || 'your-demo-name'}</small>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default MetaChat;