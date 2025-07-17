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
  List,
  Badge,
  Tabs,
  Row,
  Col,
  Statistic,
  Tooltip
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
  InfoCircleOutlined,
  BulbOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  ExperimentOutlined,
  RocketOutlined,
  BookOutlined,
  TeamOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons';
import { llmApi } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { TextArea } = Input;
const { Option } = Select;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;
const { TabPane } = Tabs;

const MetaAgentCreator = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [creationSteps, setCreationSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(null);
  const [progress, setProgress] = useState(0);
  const [agentId, setAgentId] = useState(null);
  const [error, setError] = useState(null);
  const [templates, setTemplates] = useState([]);

  useEffect(() => {
    fetchLLMProfiles();
    fetchTemplates();
  }, []);

  const fetchLLMProfiles = async () => {
    try {
      const response = await llmApi.list(true);
      // Filter only LLM profiles with JSON mode for meta agent
      const jsonProfiles = response.data.filter(profile => profile.mode === 'json');
      
      if (jsonProfiles.length === 0) {
        message.warning('No LLM profiles with JSON mode found. Please create one with mode="json".');
      }
      
      setLlmProfiles(jsonProfiles);
    } catch (error) {
      message.error('Failed to fetch LLM profiles');
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await fetch('http://localhost:8000/meta-agent/templates');
      const data = await response.json();
      setTemplates(data.templates);
    } catch (error) {
      console.error('Failed to fetch templates');
    }
  };

  const handleAnalyze = async () => {
    const values = await form.validateFields(['description', 'llm_profile']);
    setAnalyzing(true);
    setAnalysis(null);

    try {
      const response = await fetch('http://localhost:8000/meta-agent/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: values.description,
          name: values.name,
          examples: values.examples || [],
          constraints: values.constraints || [],
          llm_profile: values.llm_profile
        })
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysis(data);
        message.success('Analysis complete!');
      } else {
        message.error('Analysis failed');
      }
    } catch (error) {
      message.error('Failed to analyze requirements');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleTemplateSelect = (template) => {
    form.setFieldsValue({
      description: template.example_request,
      name: template.name.toLowerCase().replace(' ', '_')
    });
    message.info(`Template loaded: ${template.name}`);
  };

  const handleSSEMessage = (data) => {
    setCurrentStep(data);

    if (data.progress) {
      setProgress(data.progress);
    }

    // Add to timeline
    setCreationSteps(prev => [...prev, {
      ...data,
      timestamp: new Date().toLocaleTimeString()
    }]);

    // Handle different step types
    switch (data.step) {
      case 'complete':
        if (data.details?.agent_id) {
          setAgentId(data.details.agent_id);
          message.success('Agent created successfully!');
        }
        setLoading(false);
        break;

      case 'error':
        setError(data.details?.error || data.message);
        message.error('Failed to create agent');
        setLoading(false);
        break;
    }
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    setCreationSteps([]);
    setCurrentStep(null);
    setProgress(0);
    setError(null);
    setAgentId(null);

    try {
      const response = await fetch('http://localhost:8000/meta-agent/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement: {
            description: values.description,
            name: values.name,
            examples: values.examples || [],
            constraints: values.constraints || [],
            llm_profile: values.llm_profile
          },
          auto_activate: values.auto_activate !== false,
          create_missing_tools: values.create_missing_tools !== false,
          test_agent: values.test_agent !== false,
          max_tools_to_create: values.max_tools_to_create || 5
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
      message.error('Failed to create agent');
      setLoading(false);
    }
  };

  const getStepIcon = (step) => {
    const iconMap = {
      analyzing: <LoadingOutlined style={{ color: '#1890ff' }} />,
      analysis_complete: <BulbOutlined style={{ color: '#722ed1' }} />,
      identifying_tools: <ToolOutlined style={{ color: '#13c2c2' }} />,
      tools_identified: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      creating_tool: <CodeOutlined style={{ color: '#fa8c16' }} />,
      tool_created: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      tool_failed: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
      activating_service: <PlayCircleOutlined style={{ color: '#1890ff' }} />,
      creating_agent: <RobotOutlined style={{ color: '#722ed1' }} />,
      activating_agent: <ThunderboltOutlined style={{ color: '#fa8c16' }} />,
      agent_activated: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      testing_agent: <ExperimentOutlined style={{ color: '#13c2c2' }} />,
      test_complete: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      test_failed: <BugOutlined style={{ color: '#ff4d4f' }} />,
      complete: <RocketOutlined style={{ color: '#52c41a' }} />,
      error: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    };
    return iconMap[step] || <LoadingOutlined />;
  };

  const getStepColor = (step) => {
    if (step.includes('complete') || step.includes('created') || step.includes('activated')) return 'green';
    if (step.includes('error') || step.includes('failed')) return 'red';
    if (step.includes('creating') || step.includes('activating')) return 'orange';
    return 'blue';
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <RobotOutlined style={{ fontSize: '24px' }} />
            <span>Meta Agent Creator</span>
            <Tag color="purple">AI-Powered</Tag>
          </Space>
        }
      >
        <Tabs defaultActiveKey="create">
          <TabPane tab="Create Agent" key="create">
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSubmit}
              initialValues={{
                auto_activate: true,
                create_missing_tools: true,
                test_agent: true,
                max_tools_to_create: 5
              }}
            >
              <Form.Item
                name="description"
                label="What kind of agent do you need?"
                rules={[{ required: true, message: 'Please describe what the agent should do' }]}
                extra="Describe in natural language what you want the agent to accomplish"
              >
                <TextArea
                  rows={4}
                  placeholder="Example: Create a travel planning assistant that can help me find flights, hotels, and create itineraries based on my preferences and budget."
                  disabled={loading}
                />
              </Form.Item>

              <Form.Item
                name="name"
                label="Agent Name (optional)"
                extra="Leave blank to auto-generate"
              >
                <Input
                  placeholder="travel_assistant"
                  prefix={<RobotOutlined />}
                  disabled={loading}
                />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="llm_profile"
                    label="LLM Profile"
                    rules={[{ required: true, message: 'Please select an LLM profile' }]}
                    extra={
                      <Space direction="vertical" size="small">
                        <Text type="secondary">Choose which AI model to use for creating the agent</Text>
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
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="max_tools_to_create"
                    label="Max Tools to Create"
                    extra="Limit the number of new tools"
                  >
                    <Select disabled={loading}>
                      <Option value={3}>Up to 3 tools</Option>
                      <Option value={5}>Up to 5 tools</Option>
                      <Option value={10}>Up to 10 tools</Option>
                      <Option value={20}>Up to 20 tools</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Collapse ghost style={{ marginBottom: 16 }}>
                <Panel header="Advanced Options" key="1">
                  <Form.Item
                    name="examples"
                    label="Example Interactions (optional)"
                  >
                    <TextArea
                      rows={3}
                      placeholder="One example per line"
                      disabled={loading}
                    />
                  </Form.Item>

                  <Form.Item
                    name="constraints"
                    label="Constraints (optional)"
                  >
                    <TextArea
                      rows={3}
                      placeholder="One constraint per line (e.g., 'Must handle errors gracefully')"
                      disabled={loading}
                    />
                  </Form.Item>

                  <Space>
                    <Form.Item name="auto_activate" valuePropName="checked">
                      <Button type={form.getFieldValue('auto_activate') ? 'primary' : 'default'}>
                        Auto-activate
                      </Button>
                    </Form.Item>
                    <Form.Item name="create_missing_tools" valuePropName="checked">
                      <Button type={form.getFieldValue('create_missing_tools') ? 'primary' : 'default'}>
                        Create missing tools
                      </Button>
                    </Form.Item>
                    <Form.Item name="test_agent" valuePropName="checked">
                      <Button type={form.getFieldValue('test_agent') ? 'primary' : 'default'}>
                        Test after creation
                      </Button>
                    </Form.Item>
                  </Space>
                </Panel>
              </Collapse>

              <Form.Item>
                <Space size="large">
                  <Button
                    type="default"
                    onClick={handleAnalyze}
                    loading={analyzing}
                    icon={<BulbOutlined />}
                    size="large"
                  >
                    Analyze Requirements
                  </Button>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={loading}
                    icon={<SendOutlined />}
                    size="large"
                  >
                    Create Agent with AI
                  </Button>
                </Space>
              </Form.Item>
            </Form>

            {/* Analysis Results */}
            {analysis && (
              <Card
                title="Requirements Analysis"
                style={{ marginTop: 24 }}
                extra={
                  <Tag color={
                    analysis.analysis.complexity_assessment === 'simple' ? 'green' :
                    analysis.analysis.complexity_assessment === 'moderate' ? 'blue' :
                    analysis.analysis.complexity_assessment === 'complex' ? 'orange' : 'red'
                  }>
                    {analysis.analysis.complexity_assessment.toUpperCase()}
                  </Tag>
                }
              >
                <Paragraph>
                  <Text strong>Understanding: </Text>
                  {analysis.analysis.understood_purpose}
                </Paragraph>
                
                <Row gutter={16} style={{ marginTop: 16 }}>
                  <Col span={8}>
                    <Statistic
                      title="Domain"
                      value={analysis.analysis.domain}
                      prefix={<BookOutlined />}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="Tools Available"
                      value={analysis.summary.tools_available}
                      prefix={<CheckCircleOutlined />}
                      valueStyle={{ color: '#3f8600' }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="Tools to Create"
                      value={analysis.summary.tools_to_create}
                      prefix={<ToolOutlined />}
                      valueStyle={{ color: '#cf1322' }}
                    />
                  </Col>
                </Row>

                <Divider />

                <Title level={5}>Required Tools</Title>
                <List
                  size="small"
                  dataSource={[...analysis.matched_tools, ...analysis.unmatched_tools]}
                  renderItem={tool => (
                    <List.Item>
                      <Space>
                        {tool.exists ? (
                          <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        ) : (
                          <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                        )}
                        <Text strong>{tool.name}</Text>
                        <Text type="secondary">{tool.description}</Text>
                        {tool.exists && <Tag color="green">Available</Tag>}
                        {!tool.exists && <Tag color="orange">To Create</Tag>}
                      </Space>
                    </List.Item>
                  )}
                />

                <Alert
                  message="Estimated Time"
                  description={analysis.summary.estimated_time}
                  type="info"
                  showIcon
                  style={{ marginTop: 16 }}
                />
              </Card>
            )}
          </TabPane>

          <TabPane tab="Templates" key="templates">
            <List
              grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 3 }}
              dataSource={templates}
              renderItem={template => (
                <List.Item>
                  <Card
                    hoverable
                    onClick={() => handleTemplateSelect(template)}
                    actions={[
                      <Button
                        type="link"
                        icon={<ThunderboltOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleTemplateSelect(template);
                        }}
                      >
                        Use Template
                      </Button>
                    ]}
                  >
                    <Card.Meta
                      avatar={
                        <Badge count={template.complexity} style={{
                          backgroundColor: template.complexity === 'simple' ? '#52c41a' :
                            template.complexity === 'moderate' ? '#1890ff' : '#fa8c16'
                        }}>
                          <RobotOutlined style={{ fontSize: '24px' }} />
                        </Badge>
                      }
                      title={template.name}
                      description={
                        <Space direction="vertical" size="small">
                          <Paragraph ellipsis={{ rows: 2 }}>
                            {template.description}
                          </Paragraph>
                          <Space wrap>
                            <Tag color="blue">{template.domain}</Tag>
                            {template.suggested_tools.slice(0, 2).map(tool => (
                              <Tag key={tool}>{tool}</Tag>
                            ))}
                            {template.suggested_tools.length > 2 && (
                              <Tag>+{template.suggested_tools.length - 2} more</Tag>
                            )}
                          </Space>
                        </Space>
                      }
                    />
                  </Card>
                </List.Item>
              )}
            />
          </TabPane>
        </Tabs>

        {/* Creation Progress */}
        {(loading || creationSteps.length > 0) && (
          <>
            <Divider />

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

            {currentStep && (
              <Alert
                message={
                  <Space>
                    {getStepIcon(currentStep.step)}
                    <span>{currentStep.message}</span>
                  </Space>
                }
                description={currentStep.details && (
                  <Space direction="vertical" size="small">
                    {currentStep.details.existing_tools && (
                      <div>
                        <Text strong>Existing tools: </Text>
                        {currentStep.details.existing_tools.join(', ')}
                      </div>
                    )}
                    {currentStep.details.tools_to_create && (
                      <div>
                        <Text strong>Tools to create: </Text>
                        {currentStep.details.tools_to_create.join(', ')}
                      </div>
                    )}
                  </Space>
                )}
                type={error ? 'error' : 'info'}
                showIcon={false}
                style={{ marginBottom: 24 }}
              />
            )}

            <Title level={4}>
              <Space>
                <LoadingOutlined spin={loading} />
                Creation Process
              </Space>
            </Title>

            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              <Timeline mode="left">
                {creationSteps.map((step, index) => (
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
                      {step.details?.tool && (
                        <Tag color="blue">Tool: {step.details.tool}</Tag>
                      )}
                      {step.details?.service_id && (
                        <Tag color="green">Service ID: {step.details.service_id}</Tag>
                      )}
                      {step.details?.error && (
                        <Text type="danger">Error: {step.details.error}</Text>
                      )}
                    </Space>
                  </Timeline.Item>
                ))}
              </Timeline>
            </div>

            {agentId && (
              <Alert
                message="Agent Created Successfully!"
                description={
                  <Space direction="vertical">
                    <Text>Your intelligent agent has been created and is ready to use.</Text>
                    <Space>
                      <Button
                        type="primary"
                        onClick={() => navigate(`/agents/${agentId}/test`)}
                        icon={<PlayCircleOutlined />}
                      >
                        Test Agent
                      </Button>
                      <Button
                        onClick={() => navigate(`/agents`)}
                        icon={<TeamOutlined />}
                      >
                        View All Agents
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

export default MetaAgentCreator;