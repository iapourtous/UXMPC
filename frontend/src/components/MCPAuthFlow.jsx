import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Alert,
  Space,
  Steps,
  message,
  Modal,
  Form,
  Input,
  Typography,
  Tag,
  Spin,
  Row,
  Col,
  Divider
} from 'antd';
import {
  KeyOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
  LoginOutlined,
  LogoutOutlined
} from '@ant-design/icons';
import { mcpConnectionsApi } from '../services/api';

const { Step } = Steps;
const { Text, Title } = Typography;
const { TextArea } = Input;

const MCPAuthFlow = ({ connection, onAuthChange }) => {
  const [authStatus, setAuthStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [oauthFlow, setOauthFlow] = useState(null);
  const [apiKeyModalVisible, setApiKeyModalVisible] = useState(false);
  const [apiKeyForm] = Form.useForm();

  useEffect(() => {
    if (connection) {
      fetchAuthStatus();
    }
  }, [connection]);

  const fetchAuthStatus = async () => {
    if (!connection) return;
    
    setLoading(true);
    try {
      const status = await mcpConnectionsApi.getAuthStatus(connection.id);
      setAuthStatus(status);
    } catch (error) {
      message.error('Failed to fetch authentication status');
      console.error('Fetch auth status error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStartOAuth = async () => {
    if (!connection) return;

    // This would typically come from the connection configuration
    const authConfig = {
      auth_url: connection.config?.auth_url || '',
      client_id: connection.config?.client_id || '',
      redirect_uri: connection.config?.redirect_uri || `${window.location.origin}/auth/callback`,
      scope: connection.config?.scope || ''
    };

    if (!authConfig.auth_url || !authConfig.client_id) {
      message.error('OAuth configuration is incomplete. Please check the connection settings.');
      return;
    }

    setLoading(true);
    try {
      const oauthData = await mcpConnectionsApi.startOAuthFlow(connection.id, authConfig);
      setOauthFlow(oauthData);
      
      // Open OAuth URL in a new window
      const authWindow = window.open(
        oauthData.auth_url,
        'oauth_auth',
        'width=600,height=600,scrollbars=yes,resizable=yes'
      );

      // Poll for window close or message
      const pollTimer = setInterval(() => {
        if (authWindow.closed) {
          clearInterval(pollTimer);
          setLoading(false);
          // Check auth status after window closes
          setTimeout(fetchAuthStatus, 1000);
        }
      }, 1000);

      // Listen for messages from the auth window
      const messageHandler = (event) => {
        if (event.origin !== window.location.origin) return;
        
        if (event.data.type === 'oauth_success') {
          clearInterval(pollTimer);
          authWindow.close();
          setLoading(false);
          message.success('Authentication successful!');
          fetchAuthStatus();
          if (onAuthChange) onAuthChange();
        } else if (event.data.type === 'oauth_error') {
          clearInterval(pollTimer);
          authWindow.close();
          setLoading(false);
          message.error(`Authentication failed: ${event.data.error}`);
        }
      };

      window.addEventListener('message', messageHandler);
      
      // Cleanup after 5 minutes
      setTimeout(() => {
        clearInterval(pollTimer);
        window.removeEventListener('message', messageHandler);
        if (!authWindow.closed) {
          authWindow.close();
          setLoading(false);
        }
      }, 300000);

    } catch (error) {
      message.error('Failed to start OAuth flow');
      console.error('OAuth start error:', error);
      setLoading(false);
    }
  };

  const handleApiKeySubmit = async (values) => {
    if (!connection) return;

    setLoading(true);
    try {
      await mcpConnectionsApi.storeApiKey(connection.id, {
        api_key: values.api_key,
        additional_data: values.additional_data ? JSON.parse(values.additional_data) : {}
      });
      
      message.success('API key stored successfully!');
      setApiKeyModalVisible(false);
      apiKeyForm.resetFields();
      fetchAuthStatus();
      if (onAuthChange) onAuthChange();
    } catch (error) {
      message.error('Failed to store API key');
      console.error('API key store error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshToken = async () => {
    if (!connection) return;

    setLoading(true);
    try {
      await mcpConnectionsApi.refreshToken(connection.id);
      message.success('Token refreshed successfully!');
      fetchAuthStatus();
      if (onAuthChange) onAuthChange();
    } catch (error) {
      message.error('Failed to refresh token');
      console.error('Refresh token error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAuth = async () => {
    if (!connection) return;

    Modal.confirm({
      title: 'Delete Authentication',
      content: 'Are you sure you want to delete the authentication for this connection?',
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        setLoading(true);
        try {
          await mcpConnectionsApi.deleteAuth(connection.id);
          message.success('Authentication deleted successfully!');
          fetchAuthStatus();
          if (onAuthChange) onAuthChange();
        } catch (error) {
          message.error('Failed to delete authentication');
          console.error('Delete auth error:', error);
        } finally {
          setLoading(false);
        }
      }
    });
  };

  const getAuthStatusIcon = (status) => {
    if (!status) return <ExclamationCircleOutlined style={{ color: '#8c8c8c' }} />;
    
    if (status.has_auth && status.is_valid) {
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    } else if (status.has_auth && !status.is_valid) {
      return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
    } else {
      return <ExclamationCircleOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  const getAuthStatusText = (status) => {
    if (!status) return 'Unknown';
    
    if (status.has_auth && status.is_valid) {
      return 'Authenticated';
    } else if (status.has_auth && !status.is_valid) {
      return 'Token Expired';
    } else {
      return 'Not Authenticated';
    }
  };

  const getAuthStatusColor = (status) => {
    if (!status) return 'default';
    
    if (status.has_auth && status.is_valid) {
      return 'success';
    } else if (status.has_auth && !status.is_valid) {
      return 'warning';
    } else {
      return 'default';
    }
  };

  if (!connection) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Text type="secondary">No connection selected</Text>
        </div>
      </Card>
    );
  }

  if (connection.auth_type === 'none') {
    return (
      <Card>
        <Alert
          message="No Authentication Required"
          description="This connection does not require authentication."
          type="info"
          showIcon
        />
      </Card>
    );
  }

  return (
    <Card>
      <Row justify="space-between" align="middle" style={{ marginBottom: '16px' }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            Authentication for {connection.name}
          </Title>
          <Text type="secondary">
            Authentication Type: <Tag>{connection.auth_type.toUpperCase()}</Tag>
          </Text>
        </Col>
        <Col>
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchAuthStatus}
            loading={loading}
            size="small"
          >
            Refresh
          </Button>
        </Col>
      </Row>

      {loading && !authStatus ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <p style={{ marginTop: '16px' }}>Loading authentication status...</p>
        </div>
      ) : (
        <>
          <Alert
            message={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {getAuthStatusIcon(authStatus)}
                <span>Status: {getAuthStatusText(authStatus)}</span>
              </div>
            }
            description={
              authStatus && (
                <div>
                  {authStatus.expires_at && (
                    <div>Expires: {new Date(authStatus.expires_at).toLocaleString()}</div>
                  )}
                  {authStatus.scopes && authStatus.scopes.length > 0 && (
                    <div>
                      Scopes: {authStatus.scopes.map(scope => (
                        <Tag key={scope} size="small">{scope}</Tag>
                      ))}
                    </div>
                  )}
                </div>
              )
            }
            type={getAuthStatusColor(authStatus)}
            style={{ marginBottom: '16px' }}
          />

          <Divider />

          <Space direction="vertical" style={{ width: '100%' }}>
            {connection.auth_type === 'oauth' && (
              <div>
                <Button
                  type="primary"
                  icon={<LoginOutlined />}
                  onClick={handleStartOAuth}
                  loading={loading}
                  disabled={authStatus?.has_auth && authStatus?.is_valid}
                >
                  {authStatus?.has_auth ? 'Re-authenticate' : 'Start OAuth Flow'}
                </Button>
                
                {authStatus?.has_auth && !authStatus?.is_valid && (
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={handleRefreshToken}
                    loading={loading}
                    style={{ marginLeft: '8px' }}
                  >
                    Refresh Token
                  </Button>
                )}
              </div>
            )}

            {connection.auth_type === 'api_key' && (
              <div>
                <Button
                  type="primary"
                  icon={<KeyOutlined />}
                  onClick={() => setApiKeyModalVisible(true)}
                >
                  {authStatus?.has_auth ? 'Update API Key' : 'Set API Key'}
                </Button>
              </div>
            )}

            {connection.auth_type === 'basic' && (
              <div>
                <Alert
                  message="Basic Authentication"
                  description="Basic authentication is configured in the connection settings."
                  type="info"
                />
              </div>
            )}

            {authStatus?.has_auth && (
              <div>
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  onClick={handleDeleteAuth}
                  loading={loading}
                >
                  Remove Authentication
                </Button>
              </div>
            )}
          </Space>
        </>
      )}

      {/* API Key Modal */}
      <Modal
        title="API Key Authentication"
        open={apiKeyModalVisible}
        onCancel={() => {
          setApiKeyModalVisible(false);
          apiKeyForm.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form
          form={apiKeyForm}
          layout="vertical"
          onFinish={handleApiKeySubmit}
        >
          <Form.Item
            label="API Key"
            name="api_key"
            rules={[{ required: true, message: 'Please enter the API key' }]}
          >
            <Input.Password placeholder="Enter your API key" />
          </Form.Item>

          <Form.Item
            label="Additional Data (JSON)"
            name="additional_data"
            help="Optional additional authentication data as JSON"
          >
            <TextArea
              rows={4}
              placeholder='{\n  "custom_header": "value",\n  "other_param": "value"\n}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Row justify="end">
            <Space>
              <Button onClick={() => {
                setApiKeyModalVisible(false);
                apiKeyForm.resetFields();
              }}>
                Cancel
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
              >
                Save API Key
              </Button>
            </Space>
          </Row>
        </Form>
      </Modal>
    </Card>
  );
};

export default MCPAuthFlow;