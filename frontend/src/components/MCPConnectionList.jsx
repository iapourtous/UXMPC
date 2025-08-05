import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  Button,
  Card,
  Space,
  Tag,
  Popconfirm,
  message,
  Badge,
  Tooltip,
  Modal,
  Row,
  Col,
  Input,
  Dropdown,
  Divider
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ApiOutlined,
  ToolOutlined,
  FileTextOutlined,
  MessageOutlined,
  BugOutlined,
  EyeOutlined,
  SettingOutlined,
  KeyOutlined,
  LinkOutlined,
  DisconnectOutlined
} from '@ant-design/icons';
import { mcpConnectionsApi } from '../services/api';

const { Search } = Input;

const MCPConnectionList = () => {
  const navigate = useNavigate();
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [testingConnectionId, setTestingConnectionId] = useState(null);
  const [syncingConnectionId, setSyncingConnectionId] = useState(null);

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const data = await mcpConnectionsApi.listConnections();
      setConnections(data);
    } catch (error) {
      message.error('Failed to fetch MCP connections');
      console.error('Fetch connections error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await mcpConnectionsApi.deleteConnection(id);
      message.success('MCP connection deleted successfully');
      fetchConnections();
    } catch (error) {
      message.error('Failed to delete MCP connection');
      console.error('Delete connection error:', error);
    }
  };

  const handleTest = async (id) => {
    setTestingConnectionId(id);
    try {
      const result = await mcpConnectionsApi.testConnection(id);
      
      if (result.success) {
        message.success(`Connection test successful! Response time: ${result.response_time?.toFixed(2)}ms`);
      } else {
        message.error(`Connection test failed: ${result.error}`);
      }
      
      // Refresh the list to update status
      fetchConnections();
    } catch (error) {
      message.error('Failed to test connection');
      console.error('Test connection error:', error);
    } finally {
      setTestingConnectionId(null);
    }
  };

  const handleSync = async (id) => {
    setSyncingConnectionId(id);
    try {
      const result = await mcpConnectionsApi.syncConnection(id);
      message.success(
        `Sync successful! ${result.tools_count} tools, ${result.resources_count} resources, ${result.prompts_count} prompts`
      );
      fetchConnections();
    } catch (error) {
      message.error('Failed to sync connection');
      console.error('Sync connection error:', error);
    } finally {
      setSyncingConnectionId(null);
    }
  };

  const handleViewTools = (connection) => {
    Modal.info({
      title: `Tools for ${connection.name}`,
      width: 800,
      content: (
        <div>
          <p>This would show the tools available from this MCP server.</p>
          <p>Connection ID: {connection.id}</p>
          <p>Server URL: {connection.server_url}</p>
        </div>
      ),
    });
  };

  const handleManageAuth = (connection) => {
    if (connection.auth_type === 'none') {
      message.info('This connection does not require authentication');
      return;
    }

    Modal.info({
      title: `Authentication for ${connection.name}`,
      width: 600,
      content: (
        <div>
          <p>Authentication Type: <Tag>{connection.auth_type}</Tag></p>
          <p>This would show the authentication management interface.</p>
          <p>Connection ID: {connection.id}</p>
        </div>
      ),
    });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'inactive':
        return <CloseCircleOutlined style={{ color: '#8c8c8c' }} />;
      case 'auth_required':
        return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <CloseCircleOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'inactive':
        return 'default';
      case 'auth_required':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getTransportIcon = (transportType) => {
    switch (transportType) {
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

  const getAuthIcon = (authType) => {
    switch (authType) {
      case 'oauth':
        return <KeyOutlined style={{ color: '#1890ff' }} />;
      case 'api_key':
        return <KeyOutlined style={{ color: '#52c41a' }} />;
      case 'basic':
        return <KeyOutlined style={{ color: '#faad14' }} />;
      case 'none':
        return null;
      default:
        return <KeyOutlined />;
    }
  };

  const getActionMenuItems = (connection) => {
    const items = [
      {
        key: 'test',
        icon: <BugOutlined />,
        label: 'Test Connection',
        onClick: () => handleTest(connection.id),
      },
      {
        key: 'sync',
        icon: <SyncOutlined />,
        label: 'Sync Server Info',
        onClick: () => handleSync(connection.id),
      },
      {
        key: 'tools',
        icon: <ToolOutlined />,
        label: 'View Tools',
        onClick: () => handleViewTools(connection),
      },
      {
        key: 'divider1',
        type: 'divider',
      },
      {
        key: 'edit',
        icon: <EditOutlined />,
        label: 'Edit',
        onClick: () => navigate(`/mcp-connections/${connection.id}/edit`),
      }
    ];

    if (connection.auth_type !== 'none') {
      items.push({
        key: 'auth',
        icon: <KeyOutlined />,
        label: 'Manage Auth',
        onClick: () => handleManageAuth(connection),
      });
    }

    items.push(
      {
        key: 'divider2',
        type: 'divider',
      },
      {
        key: 'delete',
        icon: <DeleteOutlined />,
        label: 'Delete',
        danger: true,
        onClick: () => {
          Modal.confirm({
            title: 'Delete MCP Connection',
            content: `Are you sure you want to delete "${connection.name}"?`,
            okText: 'Delete',
            okType: 'danger',
            onOk: () => handleDelete(connection.id),
          });
        },
      }
    );

    return items;
  };

  const filteredConnections = connections.filter(connection =>
    connection.name.toLowerCase().includes(searchText.toLowerCase()) ||
    connection.description?.toLowerCase().includes(searchText.toLowerCase()) ||
    connection.server_url.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <div>
          <div style={{ fontWeight: 500 }}>{text}</div>
          {record.description && (
            <div style={{ fontSize: '12px', color: '#8c8c8c' }}>
              {record.description}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Server',
      dataIndex: 'server_url',
      key: 'server_url',
      render: (url, record) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            {getTransportIcon(record.transport_type)}
            <span style={{ fontSize: '12px' }}>{url}</span>
          </div>
          <div style={{ fontSize: '11px', color: '#8c8c8c' }}>
            {record.transport_type.toUpperCase()}
          </div>
        </div>
      ),
    },
    {
      title: 'Auth',
      dataIndex: 'auth_type',
      key: 'auth_type',
      render: (authType) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {getAuthIcon(authType)}
          <span style={{ fontSize: '12px' }}>
            {authType === 'none' ? 'None' : authType.toUpperCase()}
          </span>
        </div>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status, record) => (
        <div>
          <Badge
            status={getStatusColor(status)}
            text={
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {getStatusIcon(status)}
                {status.replace('_', ' ').toUpperCase()}
              </span>
            }
          />
          {record.last_sync && (
            <div style={{ fontSize: '11px', color: '#8c8c8c' }}>
              Last sync: {new Date(record.last_sync).toLocaleString()}
            </div>
          )}
          {record.last_error && (
            <div style={{ fontSize: '11px', color: '#ff4d4f' }}>
              Error: {record.last_error}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Tooltip title="Test Connection">
            <Button
              size="small"
              icon={<BugOutlined />}
              loading={testingConnectionId === record.id}
              onClick={() => handleTest(record.id)}
            />
          </Tooltip>
          <Tooltip title="Sync Server Info">
            <Button
              size="small"
              icon={<SyncOutlined />}
              loading={syncingConnectionId === record.id}
              onClick={() => handleSync(record.id)}
            />
          </Tooltip>
          <Dropdown
            menu={{ items: getActionMenuItems(record) }}
            trigger={['click']}
          >
            <Button size="small" icon={<SettingOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <div style={{ marginBottom: 16 }}>
        <Row justify="space-between" align="middle">
          <Col>
            <h2 style={{ margin: 0 }}>MCP Connections</h2>
            <p style={{ margin: '4px 0 0 0', color: '#8c8c8c' }}>
              Manage external MCP server connections
            </p>
          </Col>
          <Col>
            <Space>
              <Search
                placeholder="Search connections..."
                allowClear
                onChange={(e) => setSearchText(e.target.value)}
                style={{ width: 200 }}
              />
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchConnections}
                loading={loading}
              >
                Refresh
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => navigate('/mcp-connections/new')}
              >
                Add Connection
              </Button>
            </Space>
          </Col>
        </Row>
      </div>

      <Table
        columns={columns}
        dataSource={filteredConnections}
        rowKey="id"
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) =>
            `${range[0]}-${range[1]} of ${total} connections`,
        }}
        scroll={{ x: 800 }}
      />
    </Card>
  );
};

export default MCPConnectionList;