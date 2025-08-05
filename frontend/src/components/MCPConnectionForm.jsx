import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Form,
  Input,
  Button,
  Card,
  Select,
  message,
  Space,
  Row,
  Col,
  Divider,
  Alert,
  Spin,
  Tag,
  Typography,
  Collapse
} from 'antd';
import {
  SaveOutlined,
  ArrowLeftOutlined,
  ExperimentOutlined,
  ApiOutlined,
  KeyOutlined,
  LinkOutlined,
  DisconnectOutlined
} from '@ant-design/icons';
import { mcpConnectionsApi } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { Text, Title } = Typography;
const { Panel } = Collapse;

const MCPConnectionForm = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = Boolean(id);
  
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    if (isEdit) {
      fetchConnection();
    }
  }, [id, isEdit]);

  const fetchConnection = async () => {
    setInitialLoading(true);
    try {
      const connection = await mcpConnectionsApi.getConnection(id);
      form.setFieldsValue({
        name: connection.name,
        description: connection.description,
        server_url: connection.server_url,
        transport_type: connection.transport_type,
        auth_type: connection.auth_type,
        config: JSON.stringify(connection.config, null, 2)
      });
    } catch (error) {
      message.error('Failed to fetch connection details');
      console.error('Fetch connection error:', error);
    } finally {
      setInitialLoading(false);
    }
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      // Parse config JSON
      let config = {};
      if (values.config) {
        try {
          config = JSON.parse(values.config);
        } catch (e) {
          message.error('Invalid JSON in configuration');
          setLoading(false);
          return;
        }
      }

      const connectionData = {
        ...values,
        config
      };

      if (isEdit) {
        await mcpConnectionsApi.updateConnection(id, connectionData);
        message.success('MCP connection updated successfully');
      } else {
        await mcpConnectionsApi.createConnection(connectionData);
        message.success('MCP connection created successfully');
      }
      
      navigate('/mcp-connections');
    } catch (error) {
      message.error(isEdit ? 'Failed to update connection' : 'Failed to create connection');
      console.error('Submit error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    const values = form.getFieldsValue();
    
    // Validate required fields
    if (!values.name || !values.server_url) {
      message.warning('Please fill in name and server URL before testing');
      return;
    }

    setTestLoading(true);
    setTestResult(null);
    
    try {
      // If editing, test the existing connection
      if (isEdit) {
        const result = await mcpConnectionsApi.testConnection(id);
        setTestResult(result);
      } else {
        // For new connections, we would need a test endpoint that doesn't require saving
        message.info('Save the connection first to test it');
      }
    } catch (error) {
      setTestResult({
        success: false,
        error: error.message || 'Connection test failed'
      });
    } finally {
      setTestLoading(false);
    }
  };

  const getTransportDescription = (type) => {
    switch (type) {
      case 'http':
        return 'HTTP/HTTPS API endpoints';
      case 'sse':
        return 'Server-Sent Events streaming';
      case 'stdio':
        return 'Standard input/output streams';
      default:
        return '';
    }
  };

  const getAuthDescription = (type) => {
    switch (type) {
      case 'none':
        return 'No authentication required';
      case 'oauth':
        return 'OAuth 2.0 flow with access tokens';
      case 'api_key':
        return 'API key in header or query parameter';
      case 'basic':
        return 'HTTP Basic authentication';
      default:
        return '';
    }
  };

  const getTransportIcon = (type) => {
    switch (type) {
      case 'http':
        return <ApiOutlined />;
      case 'sse':
        return <LinkOutlined />;
      case 'stdio':
        return <DisconnectOutlined />;
      default:
        return <ApiOutlined />;
    }
  };

  if (initialLoading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
          <p style={{ marginTop: '16px' }}>Loading connection details...</p>
        </div>
      </Card>
    );
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <Card>
        <div style={{ marginBottom: '24px' }}>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/mcp-connections')}
            style={{ marginBottom: '16px' }}
          >
            Back to Connections
          </Button>
          <Title level={2}>
            {isEdit ? 'Edit MCP Connection' : 'New MCP Connection'}
          </Title>
          <Text type="secondary">
            {isEdit 
              ? 'Update the connection settings for this MCP server'
              : 'Create a new connection to an external MCP server'
            }
          </Text>
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            transport_type: 'sse',
            auth_type: 'none',
            config: '{}'
          }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Connection Name"
                name="name"
                rules={[{ required: true, message: 'Please enter a connection name' }]}
              >
                <Input placeholder="e.g., GitHub API, Google Drive" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Transport Type"
                name="transport_type"
                rules={[{ required: true, message: 'Please select a transport type' }]}
              >
                <Select>
                  <Option value="sse">
                    <Space>
                      <LinkOutlined />
                      Server-Sent Events
                    </Space>
                  </Option>
                  <Option value="http">
                    <Space>
                      <ApiOutlined />
                      HTTP/HTTPS
                    </Space>
                  </Option>
                  <Option value="stdio">
                    <Space>
                      <DisconnectOutlined />
                      Standard I/O
                    </Space>
                  </Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="Server URL"
            name="server_url"
            rules={[
              { required: true, message: 'Please enter the server URL' },
              { type: 'url', message: 'Please enter a valid URL' }
            ]}
          >
            <Input placeholder="https://api.example.com/mcp" />
          </Form.Item>

          <Form.Item
            label="Description"
            name="description"
          >
            <TextArea 
              rows={2} 
              placeholder="Optional description of what this MCP server provides"
            />
          </Form.Item>

          <Divider>Authentication</Divider>

          <Form.Item
            label="Authentication Type"
            name="auth_type"
            rules={[{ required: true, message: 'Please select an authentication type' }]}
          >
            <Select>
              <Option value="none">
                <Space>
                  No Authentication
                </Space>
              </Option>
              <Option value="oauth">
                <Space>
                  <KeyOutlined style={{ color: '#1890ff' }} />
                  OAuth 2.0
                </Space>
              </Option>
              <Option value="api_key">
                <Space>
                  <KeyOutlined style={{ color: '#52c41a' }} />
                  API Key
                </Space>
              </Option>
              <Option value="basic">
                <Space>
                  <KeyOutlined style={{ color: '#faad14' }} />
                  HTTP Basic
                </Space>
              </Option>
            </Select>
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prevValues, currentValues) => 
            prevValues.auth_type !== currentValues.auth_type ||
            prevValues.transport_type !== currentValues.transport_type
          }>
            {({ getFieldValue }) => {
              const authType = getFieldValue('auth_type');
              const transportType = getFieldValue('transport_type');
              
              return (
                <Alert
                  message={
                    <div>
                      <div><strong>Transport:</strong> {getTransportDescription(transportType)}</div>
                      <div><strong>Authentication:</strong> {getAuthDescription(authType)}</div>
                    </div>
                  }
                  type="info"
                  showIcon
                  style={{ marginBottom: '16px' }}
                />
              );
            }}
          </Form.Item>

          <Collapse ghost>
            <Panel header="Advanced Configuration" key="config">
              <Alert
                message="Configuration Format"
                description="Enter server-specific configuration as JSON. This may include API endpoints, timeouts, retry settings, etc."
                type="info"
                style={{ marginBottom: '16px' }}
              />
              
              <Form.Item
                label="Configuration (JSON)"
                name="config"
                rules={[
                  {
                    validator: (_, value) => {
                      if (!value) return Promise.resolve();
                      try {
                        JSON.parse(value);
                        return Promise.resolve();
                      } catch (e) {
                        return Promise.reject(new Error('Invalid JSON format'));
                      }
                    }
                  }
                ]}
              >
                <TextArea
                  rows={6}
                  placeholder='{\n  "timeout": 30,\n  "retry_attempts": 3,\n  "custom_headers": {}\n}'
                  style={{ fontFamily: 'monospace' }}
                />
              </Form.Item>
            </Panel>
          </Collapse>

          {testResult && (
            <Alert
              message={testResult.success ? 'Connection Test Successful' : 'Connection Test Failed'}
              description={
                testResult.success ? (
                  <div>
                    <div>Response time: {testResult.response_time?.toFixed(2)}ms</div>
                    {testResult.tools_count !== undefined && (
                      <div>Tools available: {testResult.tools_count}</div>
                    )}
                    {testResult.resources_count !== undefined && (
                      <div>Resources available: {testResult.resources_count}</div>
                    )}
                  </div>
                ) : (
                  testResult.error
                )
              }
              type={testResult.success ? 'success' : 'error'}
              showIcon
              style={{ marginBottom: '16px' }}
            />
          )}

          <Row justify="space-between">
            <Col>
              {isEdit && (
                <Button
                  icon={<ExperimentOutlined />}
                  onClick={handleTest}
                  loading={testLoading}
                >
                  Test Connection
                </Button>
              )}
            </Col>
            <Col>
              <Space>
                <Button onClick={() => navigate('/mcp-connections')}>
                  Cancel
                </Button>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<SaveOutlined />}
                  loading={loading}
                >
                  {isEdit ? 'Update Connection' : 'Create Connection'}
                </Button>
              </Space>
            </Col>
          </Row>
        </Form>
      </Card>
    </div>
  );
};

export default MCPConnectionForm;