import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Form, 
  Input, 
  Select, 
  Button, 
  Space, 
  Alert, 
  Progress, 
  Timeline,
  Divider,
  Typography,
  message,
  Tag,
  Collapse,
  Spin,
  Empty,
  Switch
} from 'antd';
import {
  RobotOutlined,
  SendOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  BugOutlined,
  CodeOutlined,
  PlayCircleOutlined,
  ToolOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { llmApi } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { TextArea } = Input;
const { Option } = Select;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

const AgentServiceCreator = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(null);
  const [progress, setProgress] = useState(0);
  const [serviceId, setServiceId] = useState(null);
  const [error, setError] = useState(null);
  const [useExternalApi, setUseExternalApi] = useState(false);

  useEffect(() => {
    fetchLLMProfiles();
  }, []);

  const fetchLLMProfiles = async () => {
    try {
      const response = await llmApi.list(true);
      // Filter only LLM profiles with JSON mode for agent
      const jsonProfiles = response.data.filter(profile => profile.mode === 'json');
      
      if (jsonProfiles.length === 0) {
        message.warning('No LLM profiles with JSON mode found. Please create one with mode="json".');
      }
      
      setLlmProfiles(jsonProfiles);
    } catch (error) {
      message.error('Failed to fetch LLM profiles');
    }
  };

  const handleSSEMessage = (data) => {
    // Update current step
    setCurrentStep(data);
    
    // Update progress
    if (data.progress) {
      setProgress(data.progress);
    }
    
    // Add to timeline
    setAgentSteps(prev => [...prev, {
      ...data,
      timestamp: new Date().toLocaleTimeString()
    }]);
    
    // Handle different step types
    switch (data.step) {
      case 'success':
        setServiceId(data.service_id);
        message.success('Service created successfully!');
        setLoading(false);
        break;
        
      case 'error':
        setError(data.error || data.message);
        message.error('Failed to create service');
        setLoading(false);
        break;
        
      case 'timeout':
        message.warning('Service creation timed out');
        setLoading(false);
        break;
        
      case 'completed':
        setLoading(false);
        break;
    }
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    setAgentSteps([]);
    setCurrentStep(null);
    setProgress(0);
    setError(null);
    setServiceId(null);

    try {
      // Use POST with EventSource by sending data through fetch
      const response = await fetch('http://localhost:8000/agent/create-service', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: values.name,
          description: values.description,
          service_type: values.service_type,
          llm_profile: values.llm_profile,
          // Include API fields if external API is enabled
          ...(useExternalApi && {
            api_documentation: values.api_documentation,
            api_base_url: values.api_base_url,
            api_key: values.api_key,
            api_headers: values.api_headers ? JSON.parse(values.api_headers) : null
          })
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              handleSSEMessage(data);
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }

    } catch (error) {
      setError(error.message);
      message.error('Failed to start agent');
      setLoading(false);
    }
  };

  const getStepIcon = (step) => {
    switch (step) {
      case 'analyzing':
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      case 'generating':
        return <CodeOutlined style={{ color: '#722ed1' }} />;
      case 'creating':
        return <ToolOutlined style={{ color: '#13c2c2' }} />;
      case 'activating':
        return <PlayCircleOutlined style={{ color: '#fa8c16' }} />;
      case 'testing':
        return <PlayCircleOutlined style={{ color: '#52c41a' }} />;
      case 'debugging':
        return <BugOutlined style={{ color: '#ff4d4f' }} />;
      case 'fixed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <LoadingOutlined />;
    }
  };

  const getStepColor = (step) => {
    switch (step) {
      case 'success':
      case 'fixed':
        return 'green';
      case 'error':
      case 'timeout':
        return 'red';
      case 'debugging':
        return 'orange';
      default:
        return 'blue';
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <RobotOutlined style={{ fontSize: '24px' }} />
            <span>AI Service Creator</span>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            service_type: 'tool'
          }}
        >
          <Form.Item
            name="name"
            label="Service Name"
            rules={[
              { required: true, message: 'Please enter service name' },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: 'Only alphanumeric, underscore and hyphen allowed' }
            ]}
            extra="Choose a unique name for your service"
          >
            <Input 
              placeholder="weather_service" 
              prefix={<ToolOutlined />}
              disabled={loading}
            />
          </Form.Item>

          <Form.Item
            name="description"
            label="Service Description"
            rules={[{ required: true, message: 'Please describe what the service should do' }]}
            extra="Describe in natural language what you want the service to do"
          >
            <TextArea
              rows={4}
              placeholder="Create a service that returns the current weather for a given city. It should include temperature, conditions, and humidity."
              disabled={loading}
            />
          </Form.Item>

          <Form.Item
            name="service_type"
            label="Service Type"
            rules={[{ required: true }]}
          >
            <Select disabled={loading}>
              <Option value="tool">
                <Space>
                  <Tag color="orange">Tool</Tag>
                  <span>Performs actions with parameters</span>
                </Space>
              </Option>
              <Option value="resource">
                <Space>
                  <Tag color="blue">Resource</Tag>
                  <span>Provides data content</span>
                </Space>
              </Option>
              <Option value="prompt">
                <Space>
                  <Tag color="green">Prompt</Tag>
                  <span>Generates prompts dynamically</span>
                </Space>
              </Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="llm_profile"
            label="LLM Profile"
            rules={[{ required: true, message: 'Please select an LLM profile' }]}
            extra={
              <Space direction="vertical" size="small">
                <Text type="secondary">Choose which AI model to use for creating the service</Text>
                <Text type="warning">
                  <InfoCircleOutlined /> Only LLM profiles with JSON mode are shown (required for structured responses)
                </Text>
              </Space>
            }
          >
            <Select
              placeholder="Select LLM profile (JSON mode)"
              disabled={loading}
              showSearch
              optionFilterProp="children"
              notFoundContent={
                <Empty 
                  description="No JSON-mode LLM profiles found"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                >
                  <Button 
                    type="link" 
                    onClick={() => navigate('/llms/new')}
                  >
                    Create LLM Profile
                  </Button>
                </Empty>
              }
            >
              {llmProfiles.map(profile => (
                <Option key={profile.name} value={profile.name}>
                  <Space>
                    <Tag color="purple">{profile.model}</Tag>
                    <Tag color="green">JSON</Tag>
                    {profile.name}
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>

          {/* External API Configuration */}
          <Card
            style={{ marginBottom: 24 }}
            size="small"
            title={
              <Space>
                <Switch
                  checked={useExternalApi}
                  onChange={setUseExternalApi}
                />
                <Text>Use External API</Text>
              </Space>
            }
            extra={<Text type="secondary">Configure if your service needs to call external APIs</Text>}
          >
            {useExternalApi && (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Form.Item
                  name="api_documentation"
                  label="API Documentation"
                  rules={[
                    { required: useExternalApi, message: 'Please provide API documentation' }
                  ]}
                  extra="Paste the API documentation or endpoint details here"
                >
                  <TextArea
                    rows={6}
                    placeholder="Example:
GET https://api.example.com/v2/data/{id}

Parameters:
- id: The resource ID (required)
- format: Response format (json/xml)

Headers:
- X-API-Key: Your API key

Response:
{
  'data': {...},
  'status': 'success'
}"
                    disabled={loading}
                  />
                </Form.Item>

                <Form.Item
                  name="api_base_url"
                  label="API Base URL"
                  rules={[
                    { required: useExternalApi, message: 'Please provide API base URL' },
                    { type: 'url', message: 'Please enter a valid URL' }
                  ]}
                  extra="The base URL of the API (e.g., https://api.example.com)"
                >
                  <Input
                    placeholder="https://api.example.com"
                    disabled={loading}
                  />
                </Form.Item>

                <Form.Item
                  name="api_key"
                  label="API Key (Optional)"
                  extra="If the API requires authentication, provide the API key"
                >
                  <Input.Password
                    placeholder="Your API key"
                    disabled={loading}
                  />
                </Form.Item>

                <Form.Item
                  name="api_headers"
                  label="Custom Headers (Optional)"
                  extra="Additional headers in JSON format (e.g., {'X-Custom-Header': 'value'})"
                >
                  <TextArea
                    rows={3}
                    placeholder='{"X-Custom-Header": "value", "Accept": "application/json"}'
                    disabled={loading}
                  />
                </Form.Item>
              </Space>
            )}
          </Card>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              icon={<SendOutlined />}
              size="large"
              block
            >
              Create Service with AI
            </Button>
          </Form.Item>
        </Form>

        {(loading || agentSteps.length > 0) && (
          <>
            <Divider />
            
            {/* Progress Bar */}
            {loading && (
              <div style={{ marginBottom: 24 }}>
                <Progress 
                  percent={progress} 
                  status={error ? 'exception' : 'active'}
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#87d068',
                  }}
                />
              </div>
            )}

            {/* Current Status */}
            {currentStep && (
              <Alert
                message={
                  <Space>
                    {getStepIcon(currentStep.step)}
                    <span>{currentStep.message}</span>
                  </Space>
                }
                description={currentStep.details && (
                  <Paragraph style={{ marginBottom: 0 }}>
                    {JSON.stringify(currentStep.details, null, 2)}
                  </Paragraph>
                )}
                type={error ? 'error' : 'info'}
                showIcon={false}
                style={{ marginBottom: 24 }}
              />
            )}

            {/* Agent Timeline */}
            <Title level={4}>
              <Space>
                <LoadingOutlined spin={loading} />
                Agent Activity Log
              </Space>
            </Title>
            
            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              <Timeline mode="left">
                {agentSteps.map((step, index) => (
                  <Timeline.Item
                    key={index}
                    color={getStepColor(step.step)}
                    dot={getStepIcon(step.step)}
                  >
                    <Space direction="vertical" size="small">
                      <Space>
                        <Text strong>{step.message}</Text>
                        <Text type="secondary">{step.timestamp}</Text>
                      </Space>
                      {step.fix && (
                        <Tag color="green">Fix: {step.fix}</Tag>
                      )}
                      {step.error && (
                        <Text type="danger">Error: {step.error}</Text>
                      )}
                      {step.test_result && (
                        <Collapse ghost>
                          <Panel header="Test Result" key="1">
                            <pre style={{ fontSize: '12px' }}>
                              {JSON.stringify(step.test_result, null, 2)}
                            </pre>
                          </Panel>
                        </Collapse>
                      )}
                    </Space>
                  </Timeline.Item>
                ))}
              </Timeline>
            </div>

            {/* Success Actions */}
            {serviceId && (
              <Alert
                message="Service Created Successfully!"
                description={
                  <Space direction="vertical">
                    <Text>Your service has been created and tested successfully.</Text>
                    <Space>
                      <Button
                        type="primary"
                        onClick={() => navigate(`/services/${serviceId}/edit`)}
                      >
                        View Service
                      </Button>
                      <Button onClick={() => navigate('/services')}>
                        Go to Services
                      </Button>
                    </Space>
                  </Space>
                }
                type="success"
                showIcon
                style={{ marginTop: 24 }}
              />
            )}
          </>
        )}
      </Card>
    </div>
  );
};

export default AgentServiceCreator;