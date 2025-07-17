import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Space,
  Switch,
  message,
  InputNumber,
  Row,
  Col,
  Alert,
  Divider,
  Typography,
  Tooltip
} from 'antd';
import {
  SaveOutlined,
  CloseOutlined,
  DatabaseOutlined,
  KeyOutlined,
  ApiOutlined,
  FireOutlined,
  InfoCircleOutlined,
  RobotOutlined,
  CheckCircleOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { llmApi } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { Title, Text } = Typography;

const LLMProfileFormAntd = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [endpointType, setEndpointType] = useState('openai');

  useEffect(() => {
    if (id) {
      fetchProfile();
    }
  }, [id]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const response = await llmApi.get(id);
      const profile = response.data;
      
      // Determine endpoint type
      if (!profile.endpoint || profile.endpoint.includes('openai')) {
        setEndpointType('openai');
      } else if (profile.endpoint.includes('anthropic')) {
        setEndpointType('anthropic');
      } else if (profile.endpoint.includes('openrouter')) {
        setEndpointType('openrouter');
      } else {
        setEndpointType('custom');
      }
      
      form.setFieldsValue(profile);
    } catch (error) {
      message.error('Failed to fetch LLM profile');
      navigate('/llms');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      // Convert model array to string if needed (from tags mode)
      if (Array.isArray(values.model)) {
        values.model = values.model[0] || '';
      }
      
      // Set endpoint based on type
      if (endpointType === 'openai') {
        values.endpoint = null; // Use default
      } else if (endpointType === 'anthropic') {
        values.endpoint = 'https://api.anthropic.com/v1/messages';
      } else if (endpointType === 'openrouter') {
        values.endpoint = 'https://openrouter.ai/api/v1/chat/completions';
      }
      // For custom, keep the user-provided endpoint

      if (id) {
        // For update, exclude the name field since it's disabled
        const { name, ...updateData } = values;
        await llmApi.update(id, updateData);
        message.success('LLM profile updated successfully');
      } else {
        await llmApi.create(values);
        message.success('LLM profile created successfully');
      }
      navigate('/llms');
    } catch (error) {
      let errorMessage = id ? 'Failed to update LLM profile' : 'Failed to create LLM profile';
      
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          // FastAPI validation errors come as an array
          errorMessage = error.response.data.detail.map(err => 
            `${err.loc?.join('.') || 'Field'}: ${err.msg}`
          ).join(', ');
        } else {
          errorMessage = error.response.data.detail;
        }
      }
      
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const commonModels = {
    openai: [
      'gpt-4-turbo-preview',
      'gpt-4',
      'gpt-3.5-turbo',
      'gpt-3.5-turbo-16k'
    ],
    anthropic: [
      'claude-3-opus-20240229',
      'claude-3-sonnet-20240229',
      'claude-3-haiku-20240307',
      'claude-2.1',
      'claude-2.0'
    ],
    openrouter: [
      'anthropic/claude-4-opus-20250522',
      'openai/gpt-4-turbo',
      'google/gemini-pro',
      'meta-llama/llama-3-70b-instruct'
    ]
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <DatabaseOutlined style={{ fontSize: '24px' }} />
            <span>{id ? 'Edit LLM Profile' : 'Create LLM Profile'}</span>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            temperature: 0.7,
            max_tokens: 4096,
            mode: 'json',
            active: true
          }}
        >
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="Profile Name"
                rules={[
                  { required: true, message: 'Please enter profile name' },
                  { pattern: /^[a-zA-Z0-9_\- ]+$/, message: 'Only alphanumeric, underscore, hyphen and space allowed' }
                ]}
              >
                <Input
                  prefix={<DatabaseOutlined />}
                  placeholder="My LLM Profile"
                  disabled={!!id}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="active"
                label="Status"
                valuePropName="checked"
              >
                <Switch checkedChildren="Active" unCheckedChildren="Inactive" />
              </Form.Item>
            </Col>
          </Row>

          <Divider>Model Configuration</Divider>

          <Row gutter={24}>
            <Col span={12}>
              <Form.Item label="Provider">
                <Select value={endpointType} onChange={setEndpointType}>
                  <Option value="openai">
                    <Space>
                      <span>🤖</span>
                      OpenAI
                    </Space>
                  </Option>
                  <Option value="anthropic">
                    <Space>
                      <span>🧠</span>
                      Anthropic
                    </Space>
                  </Option>
                  <Option value="openrouter">
                    <Space>
                      <span>🌐</span>
                      OpenRouter
                    </Space>
                  </Option>
                  <Option value="custom">
                    <Space>
                      <ApiOutlined />
                      Custom Endpoint
                    </Space>
                  </Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="model"
                label="Model"
                rules={[{ required: true, message: 'Please enter or select model' }]}
              >
                <Select
                  showSearch
                  placeholder="Select or enter model name"
                  mode="tags"
                  maxTagCount={1}
                >
                  {(commonModels[endpointType] || []).map(model => (
                    <Option key={model} value={model}>
                      <Space>
                        <RobotOutlined />
                        {model}
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          {endpointType === 'custom' && (
            <Form.Item
              name="endpoint"
              label="Custom Endpoint URL"
              rules={[
                { required: true, message: 'Please enter endpoint URL' },
                { type: 'url', message: 'Please enter a valid URL' }
              ]}
            >
              <Input
                prefix={<ApiOutlined />}
                placeholder="https://api.example.com/v1/chat/completions"
              />
            </Form.Item>
          )}

          <Form.Item
            name="api_key"
            label={
              <Space>
                API Key
                <Tooltip title="Your API key is stored securely">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            }
            rules={[{ required: true, message: 'Please enter API key' }]}
          >
            <Input.Password
              prefix={<KeyOutlined />}
              placeholder="sk-..."
            />
          </Form.Item>

          <Divider>Generation Settings</Divider>

          <Row gutter={24}>
            <Col span={8}>
              <Form.Item
                name="temperature"
                label={
                  <Space>
                    Temperature
                    <Tooltip title="Controls randomness. Lower = more focused, Higher = more creative">
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
                  prefix={<FireOutlined />}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="max_tokens"
                label={
                  <Space>
                    Max Tokens
                    <Tooltip title="Maximum number of tokens to generate">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
              >
                <InputNumber
                  min={1}
                  max={128000}
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="mode"
                label={
                  <Space>
                    Response Mode
                    <Tooltip title="JSON mode is required for AI Agent service creation">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
              >
                <Select>
                  <Option value="json">
                    <Space>
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      JSON (Recommended for AI Agent)
                    </Space>
                  </Option>
                  <Option value="text">
                    <Space>
                      <FileTextOutlined />
                      Text
                    </Space>
                  </Option>
                  <Option value="markdown">
                    <Space>
                      <FileTextOutlined />
                      Markdown
                    </Space>
                  </Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="system_prompt"
            label={
              <Space>
                System Prompt
                <Tooltip title="Instructions that define the AI's behavior">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            }
          >
            <TextArea
              rows={6}
              placeholder="You are a helpful assistant..."
              showCount
              maxLength={2000}
            />
          </Form.Item>

          <Form.Item
            name="description"
            label="Description"
          >
            <TextArea
              rows={2}
              placeholder="Describe the purpose of this LLM profile..."
            />
          </Form.Item>

          <Divider />

          {!id && (
            <Alert
              message="Tips"
              description={
                <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                  <li>Choose a descriptive name for easy identification</li>
                  <li>System prompts help maintain consistent behavior</li>
                  <li>Lower temperature (0.0-0.5) for factual responses</li>
                  <li>Higher temperature (0.7-1.0) for creative responses</li>
                </ul>
              }
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
                {id ? 'Update Profile' : 'Create Profile'}
              </Button>
              <Button
                onClick={() => navigate('/llms')}
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

export default LLMProfileFormAntd;