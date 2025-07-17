import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Form,
  Input,
  Button,
  Select,
  Card,
  Space,
  message,
  Switch,
  InputNumber,
  Divider,
  Row,
  Col,
  Typography,
  Alert,
  Tooltip,
  Tag,
  Slider,
  Radio
} from 'antd';
import {
  SaveOutlined,
  CloseOutlined,
  RobotOutlined,
  ApiOutlined,
  ToolOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  BookOutlined,
  BulbOutlined,
  StopOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  SmileOutlined,
  SettingOutlined
} from '@ant-design/icons';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { agentsApi, llmApi, servicesApi } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { Title, Text } = Typography;

const AgentForm = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [services, setServices] = useState([]);
  const [inputSchemaType, setInputSchemaType] = useState('text');
  const [outputSchemaType, setOutputSchemaType] = useState('text');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showPersonality, setShowPersonality] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [objectives, setObjectives] = useState(['']);
  const [constraints, setConstraints] = useState(['']);

  useEffect(() => {
    fetchDependencies();
    if (id) {
      fetchAgent();
    }
  }, [id]);

  const fetchDependencies = async () => {
    try {
      const [llmResponse, servicesResponse] = await Promise.all([
        llmApi.list(true), // Only active LLM profiles
        servicesApi.list(true) // Only active services
      ]);
      setLlmProfiles(llmResponse.data);
      setServices(servicesResponse.data);
    } catch (error) {
      message.error('Failed to fetch dependencies');
    }
  };

  const fetchAgent = async () => {
    setLoading(true);
    try {
      const response = await agentsApi.get(id);
      const agent = response.data;
      
      // Set schema types
      setInputSchemaType(agent.input_schema === 'text' ? 'text' : 'json');
      setOutputSchemaType(agent.output_schema === 'text' ? 'text' : 'json');
      
      // Set objectives and constraints
      if (agent.objectives && agent.objectives.length > 0) {
        setObjectives(agent.objectives);
      }
      if (agent.constraints && agent.constraints.length > 0) {
        setConstraints(agent.constraints);
      }
      
      // Set form values
      form.setFieldsValue({
        ...agent,
        input_schema: agent.input_schema === 'text' ? undefined : JSON.stringify(agent.input_schema, null, 2),
        output_schema: agent.output_schema === 'text' ? undefined : JSON.stringify(agent.output_schema, null, 2)
      });
      
      if (agent.temperature || agent.max_tokens || agent.max_iterations !== 5) {
        setShowAdvanced(true);
      }
      
      if (agent.backstory || agent.memory_enabled || agent.reasoning_strategy !== 'standard') {
        setShowPersonality(true);
      }
      
      if (agent.memory_enabled) {
        setShowMemory(true);
      }
    } catch (error) {
      message.error('Failed to fetch agent');
      navigate('/agents');
    } finally {
      setLoading(false);
    }
  };

  const addObjective = () => {
    setObjectives([...objectives, '']);
  };

  const removeObjective = (index) => {
    setObjectives(objectives.filter((_, i) => i !== index));
  };

  const updateObjective = (index, value) => {
    const newObjectives = [...objectives];
    newObjectives[index] = value;
    setObjectives(newObjectives);
  };

  const addConstraint = () => {
    setConstraints([...constraints, '']);
  };

  const removeConstraint = (index) => {
    setConstraints(constraints.filter((_, i) => i !== index));
  };

  const updateConstraint = (index, value) => {
    const newConstraints = [...constraints];
    newConstraints[index] = value;
    setConstraints(newConstraints);
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      // Process schemas
      const processedValues = {
        ...values,
        input_schema: inputSchemaType === 'text' ? 'text' : JSON.parse(values.input_schema || '{}'),
        output_schema: outputSchemaType === 'text' ? 'text' : JSON.parse(values.output_schema || '{}'),
        objectives: objectives.filter(obj => obj.trim() !== ''),
        constraints: constraints.filter(con => con.trim() !== ''),
        personality_traits: {
          tone: values.tone || 'professional',
          verbosity: values.verbosity || 'balanced',
          empathy: values.empathy || 'moderate',
          humor: values.humor || 'none'
        },
        decision_policies: {
          confidence_threshold: values.confidence_threshold || 0.8,
          require_confirmation: values.require_confirmation || [],
          auto_correct_errors: values.auto_correct_errors !== false,
          explain_decisions: values.explain_decisions || false,
          max_retries: values.max_retries || 3
        },
        memory_config: values.memory_enabled ? {
          max_memories: values.max_memories || 1000,
          embedding_model: values.embedding_model || 'all-MiniLM-L6-v2',
          search_k: values.search_k || 5
        } : undefined
      };

      if (id) {
        await agentsApi.update(id, processedValues);
        message.success('Agent updated successfully');
      } else {
        await agentsApi.create(processedValues);
        message.success('Agent created successfully');
      }
      navigate('/agents');
    } catch (error) {
      if (error.response?.data?.detail) {
        message.error(error.response.data.detail);
      } else {
        message.error(id ? 'Failed to update agent' : 'Failed to create agent');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <RobotOutlined style={{ fontSize: '24px' }} />
            <span>{id ? 'Edit Agent' : 'Create Agent'}</span>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            active: false,
            allow_parallel_tool_calls: true,
            require_tool_use: false,
            max_iterations: 5,
            memory_enabled: false,
            reasoning_strategy: 'standard',
            tone: 'professional',
            verbosity: 'balanced',
            empathy: 'moderate',
            humor: 'none',
            confidence_threshold: 0.8,
            auto_correct_errors: true,
            explain_decisions: false,
            max_retries: 3,
            max_memories: 1000,
            embedding_model: 'all-MiniLM-L6-v2',
            search_k: 5
          }}
        >
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="Agent Name"
                rules={[
                  { required: true, message: 'Please enter agent name' },
                  { pattern: /^[a-zA-Z0-9_-]+$/, message: 'Only alphanumeric, underscore and hyphen allowed' }
                ]}
              >
                <Input
                  prefix={<RobotOutlined />}
                  placeholder="my-agent"
                  disabled={!!id}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="endpoint"
                label="API Endpoint"
                rules={[
                  { required: true, message: 'Please enter API endpoint' },
                  { pattern: /^\//, message: 'Endpoint must start with /' }
                ]}
                extra="This will be the HTTP endpoint for your agent"
              >
                <Input
                  prefix={<ApiOutlined />}
                  placeholder="/api/agents/my-agent"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="description"
            label="Description"
          >
            <TextArea
              rows={2}
              placeholder="Describe what this agent does..."
            />
          </Form.Item>

          <Divider>Core Configuration</Divider>

          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="llm_profile"
                label="LLM Profile"
                rules={[{ required: true, message: 'Please select an LLM profile' }]}
              >
                <Select
                  placeholder="Select LLM profile"
                  showSearch
                  optionFilterProp="children"
                >
                  {llmProfiles.map(profile => (
                    <Option key={profile.name} value={profile.name}>
                      <Space>
                        <Tag color="purple">{profile.model}</Tag>
                        {profile.name}
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="mcp_services"
                label={
                  <Space>
                    MCP Services
                    <Tooltip title="Select the MCP services this agent can use as tools">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
              >
                <Select
                  mode="multiple"
                  placeholder="Select services to use as tools"
                  showSearch
                  optionFilterProp="children"
                >
                  {services.map(service => (
                    <Option key={service.name} value={service.name}>
                      <Space>
                        <ToolOutlined />
                        {service.name}
                        <Text type="secondary">({service.service_type})</Text>
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider>Prompts</Divider>

          <Form.Item
            name="system_prompt"
            label={
              <Space>
                System Prompt
                <Tooltip title="System-level instructions for the agent">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            }
          >
            <TextArea
              rows={4}
              placeholder="You are a helpful assistant that..."
            />
          </Form.Item>

          <Form.Item
            name="pre_prompt"
            label={
              <Space>
                Pre-prompt
                <Tooltip title="Text prepended to each user message">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            }
          >
            <TextArea
              rows={3}
              placeholder="Additional context or instructions added before user input..."
            />
          </Form.Item>

          <Divider>
            <Space>
              <BookOutlined />
              Agent Identity & Behavior
            </Space>
            <Switch
              size="small"
              checked={showPersonality}
              onChange={setShowPersonality}
              style={{ marginLeft: 16 }}
            />
          </Divider>

          {showPersonality && (
            <>
              <Form.Item
                name="backstory"
                label={
                  <Space>
                    Backstory
                    <Tooltip title="Agent's identity, background, and context">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
              >
                <TextArea
                  rows={3}
                  placeholder="I am an experienced assistant with expertise in..."
                />
              </Form.Item>

              <Form.Item label="Objectives">
                <Space direction="vertical" style={{ width: '100%' }}>
                  {objectives.map((obj, index) => (
                    <Space key={index} style={{ width: '100%' }}>
                      <Input
                        value={obj}
                        onChange={(e) => updateObjective(index, e.target.value)}
                        placeholder="Enter an objective..."
                        style={{ flex: 1 }}
                      />
                      <Button
                        danger
                        onClick={() => removeObjective(index)}
                        disabled={objectives.length <= 1}
                      >
                        Remove
                      </Button>
                    </Space>
                  ))}
                  <Button type="dashed" onClick={addObjective} style={{ width: '100%' }}>
                    <BulbOutlined /> Add Objective
                  </Button>
                </Space>
              </Form.Item>

              <Form.Item label="Constraints">
                <Space direction="vertical" style={{ width: '100%' }}>
                  {constraints.map((con, index) => (
                    <Space key={index} style={{ width: '100%' }}>
                      <Input
                        value={con}
                        onChange={(e) => updateConstraint(index, e.target.value)}
                        placeholder="Enter a constraint..."
                        style={{ flex: 1 }}
                      />
                      <Button
                        danger
                        onClick={() => removeConstraint(index)}
                        disabled={constraints.length <= 1}
                      >
                        Remove
                      </Button>
                    </Space>
                  ))}
                  <Button type="dashed" onClick={addConstraint} style={{ width: '100%' }}>
                    <StopOutlined /> Add Constraint
                  </Button>
                </Space>
              </Form.Item>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="reasoning_strategy"
                    label={
                      <Space>
                        Reasoning Strategy
                        <Tooltip title="How the agent processes information">
                          <InfoCircleOutlined />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <Select>
                      <Option value="standard">Standard</Option>
                      <Option value="chain-of-thought">Chain of Thought</Option>
                      <Option value="tree-of-thought">Tree of Thought</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="memory_enabled"
                    label="Memory"
                    valuePropName="checked"
                  >
                    <Space>
                      <Switch onChange={setShowMemory} />
                      <span>Enable Persistent Memory</span>
                    </Space>
                  </Form.Item>
                </Col>
              </Row>

              <Divider orientation="left">
                <SmileOutlined /> Personality Traits
              </Divider>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="tone"
                    label="Communication Tone"
                  >
                    <Radio.Group>
                      <Radio value="professional">Professional</Radio>
                      <Radio value="friendly">Friendly</Radio>
                      <Radio value="casual">Casual</Radio>
                    </Radio.Group>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="verbosity"
                    label="Response Detail"
                  >
                    <Radio.Group>
                      <Radio value="concise">Concise</Radio>
                      <Radio value="balanced">Balanced</Radio>
                      <Radio value="detailed">Detailed</Radio>
                    </Radio.Group>
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="empathy"
                    label="Empathy Level"
                  >
                    <Radio.Group>
                      <Radio value="low">Low</Radio>
                      <Radio value="moderate">Moderate</Radio>
                      <Radio value="high">High</Radio>
                    </Radio.Group>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="humor"
                    label="Humor Style"
                  >
                    <Radio.Group>
                      <Radio value="none">None</Radio>
                      <Radio value="subtle">Subtle</Radio>
                      <Radio value="moderate">Moderate</Radio>
                    </Radio.Group>
                  </Form.Item>
                </Col>
              </Row>

              <Divider orientation="left">
                <SettingOutlined /> Decision Policies
              </Divider>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="confidence_threshold"
                    label={
                      <Space>
                        Confidence Threshold
                        <Tooltip title="Minimum confidence required for decisions (0-1)">
                          <InfoCircleOutlined />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <Slider
                      min={0}
                      max={1}
                      step={0.05}
                      marks={{
                        0: '0',
                        0.5: '0.5',
                        0.8: '0.8',
                        1: '1'
                      }}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="max_retries"
                    label={
                      <Space>
                        Max Retries
                        <Tooltip title="Maximum retry attempts for failed operations">
                          <InfoCircleOutlined />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <InputNumber
                      min={0}
                      max={10}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="auto_correct_errors"
                    valuePropName="checked"
                  >
                    <Space>
                      <Switch />
                      <span>Auto-correct Errors</span>
                    </Space>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="explain_decisions"
                    valuePropName="checked"
                  >
                    <Space>
                      <Switch />
                      <span>Explain Decisions</span>
                    </Space>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="require_confirmation"
                label={
                  <Space>
                    Require Confirmation For
                    <Tooltip title="Actions that require user confirmation">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
              >
                <Select mode="multiple" placeholder="Select actions requiring confirmation">
                  <Option value="delete">Delete Operations</Option>
                  <Option value="modify">Modify Operations</Option>
                  <Option value="create">Create Operations</Option>
                  <Option value="execute">Execute Commands</Option>
                </Select>
              </Form.Item>
            </>
          )}

          {showMemory && (
            <>
              <Divider orientation="left">
                <DatabaseOutlined /> Memory Configuration
              </Divider>

              <Row gutter={24}>
                <Col span={8}>
                  <Form.Item
                    name="max_memories"
                    label="Max Memories"
                  >
                    <InputNumber
                      min={100}
                      max={10000}
                      step={100}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="search_k"
                    label="Memory Search Results"
                  >
                    <InputNumber
                      min={1}
                      max={20}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="embedding_model"
                    label="Embedding Model"
                  >
                    <Select>
                      <Option value="all-MiniLM-L6-v2">all-MiniLM-L6-v2</Option>
                      <Option value="all-mpnet-base-v2">all-mpnet-base-v2</Option>
                      <Option value="paraphrase-MiniLM-L6-v2">paraphrase-MiniLM-L6-v2</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}

          <Divider>Input/Output Schema</Divider>

          <Row gutter={24}>
            <Col span={12}>
              <Form.Item label="Input Schema Type">
                <Select value={inputSchemaType} onChange={setInputSchemaType}>
                  <Option value="text">Plain Text</Option>
                  <Option value="json">JSON Schema</Option>
                </Select>
              </Form.Item>
              {inputSchemaType === 'json' && (
                <Form.Item
                  name="input_schema"
                  label="Input JSON Schema"
                  rules={[
                    {
                      validator: (_, value) => {
                        if (!value) return Promise.resolve();
                        try {
                          JSON.parse(value);
                          return Promise.resolve();
                        } catch {
                          return Promise.reject('Invalid JSON');
                        }
                      }
                    }
                  ]}
                >
                  <CodeMirror
                    height="200px"
                    extensions={[json()]}
                    placeholder={JSON.stringify({
                      type: "object",
                      properties: {
                        query: { type: "string" }
                      },
                      required: ["query"]
                    }, null, 2)}
                  />
                </Form.Item>
              )}
            </Col>
            <Col span={12}>
              <Form.Item label="Output Schema Type">
                <Select value={outputSchemaType} onChange={setOutputSchemaType}>
                  <Option value="text">Plain Text</Option>
                  <Option value="json">JSON Schema</Option>
                </Select>
              </Form.Item>
              {outputSchemaType === 'json' && (
                <Form.Item
                  name="output_schema"
                  label="Output JSON Schema"
                  rules={[
                    {
                      validator: (_, value) => {
                        if (!value) return Promise.resolve();
                        try {
                          JSON.parse(value);
                          return Promise.resolve();
                        } catch {
                          return Promise.reject('Invalid JSON');
                        }
                      }
                    }
                  ]}
                >
                  <CodeMirror
                    height="200px"
                    extensions={[json()]}
                    placeholder={JSON.stringify({
                      type: "object",
                      properties: {
                        result: { type: "string" }
                      }
                    }, null, 2)}
                  />
                </Form.Item>
              )}
            </Col>
          </Row>

          <Divider>
            Advanced Settings
            <Switch
              size="small"
              checked={showAdvanced}
              onChange={setShowAdvanced}
              style={{ marginLeft: 16 }}
            />
          </Divider>

          {showAdvanced && (
            <>
              <Row gutter={24}>
                <Col span={8}>
                  <Form.Item
                    name="temperature"
                    label={
                      <Space>
                        Temperature
                        <Tooltip title="Override LLM temperature (0-2)">
                          <InfoCircleOutlined />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <InputNumber
                      min={0}
                      max={2}
                      step={0.1}
                      style={{ width: '100%' }}
                      placeholder="Use LLM default"
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="max_tokens"
                    label={
                      <Space>
                        Max Tokens
                        <Tooltip title="Override max tokens">
                          <InfoCircleOutlined />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <InputNumber
                      min={1}
                      max={32000}
                      style={{ width: '100%' }}
                      placeholder="Use LLM default"
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="max_iterations"
                    label={
                      <Space>
                        Max Iterations
                        <Tooltip title="Maximum tool use iterations">
                          <InfoCircleOutlined />
                        </Tooltip>
                      </Space>
                    }
                  >
                    <InputNumber
                      min={1}
                      max={20}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="allow_parallel_tool_calls"
                    valuePropName="checked"
                  >
                    <Space>
                      <Switch />
                      <span>Allow Parallel Tool Calls</span>
                    </Space>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="require_tool_use"
                    valuePropName="checked"
                  >
                    <Space>
                      <Switch />
                      <span>Require Tool Use</span>
                    </Space>
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}

          {!id && (
            <Alert
              message="Note"
              description="After creating the agent, you'll need to activate it to make the endpoint available."
              type="info"
              showIcon
              style={{ marginBottom: 24 }}
            />
          )}

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<SaveOutlined />}
              >
                {id ? 'Update Agent' : 'Create Agent'}
              </Button>
              <Button
                onClick={() => navigate('/agents')}
                icon={<CloseOutlined />}
              >
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default AgentForm;