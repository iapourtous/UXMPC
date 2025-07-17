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
  Input,
  Row,
  Col,
  Statistic,
  Tooltip
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  DatabaseOutlined,
  KeyOutlined,
  ApiOutlined,
  FireOutlined,
  RobotOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';
import { llmApi } from '../services/api';

const { Search } = Input;

const LLMProfileListAntd = () => {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    fetchProfiles();
  }, []);

  const fetchProfiles = async () => {
    setLoading(true);
    try {
      const response = await llmApi.list();
      setProfiles(response.data);
    } catch (error) {
      message.error('Failed to fetch LLM profiles');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (profile) => {
    try {
      await llmApi.delete(profile.id);
      message.success(`LLM profile "${profile.name}" deleted`);
      fetchProfiles();
    } catch (error) {
      message.error('Failed to delete LLM profile');
    }
  };

  const getModelIcon = (model) => {
    if (model.includes('gpt')) return '🤖';
    if (model.includes('claude')) return '🧠';
    if (model.includes('llama')) return '🦙';
    if (model.includes('mistral')) return '🌟';
    return '🤖';
  };

  const getEndpointType = (endpoint) => {
    if (!endpoint) return { label: 'Default', color: 'default' };
    if (endpoint.includes('openai')) return { label: 'OpenAI', color: 'green' };
    if (endpoint.includes('anthropic')) return { label: 'Anthropic', color: 'blue' };
    if (endpoint.includes('openrouter')) return { label: 'OpenRouter', color: 'purple' };
    if (endpoint.includes('localhost')) return { label: 'Local', color: 'orange' };
    return { label: 'Custom', color: 'cyan' };
  };

  const filteredProfiles = profiles.filter(profile =>
    !searchText || 
    profile.name.toLowerCase().includes(searchText.toLowerCase()) ||
    profile.model.toLowerCase().includes(searchText.toLowerCase()) ||
    profile.description?.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <span style={{ fontSize: '20px' }}>{getModelIcon(record.model)}</span>
          <strong>{text}</strong>
        </Space>
      )
    },
    {
      title: 'Model',
      dataIndex: 'model',
      key: 'model',
      render: (model) => (
        <Tag color="purple" icon={<RobotOutlined />}>
          {model}
        </Tag>
      )
    },
    {
      title: 'Endpoint',
      dataIndex: 'endpoint',
      key: 'endpoint',
      render: (endpoint) => {
        const endpointType = getEndpointType(endpoint);
        return (
          <Tag color={endpointType.color} icon={<ApiOutlined />}>
            {endpointType.label}
          </Tag>
        );
      }
    },
    {
      title: 'Temperature',
      dataIndex: 'temperature',
      key: 'temperature',
      width: 120,
      render: (temp) => (
        <Tag color={temp > 0.7 ? 'red' : temp > 0.3 ? 'orange' : 'blue'}>
          <FireOutlined /> {temp}
        </Tag>
      )
    },
    {
      title: 'Max Tokens',
      dataIndex: 'max_tokens',
      key: 'max_tokens',
      width: 120,
      render: (tokens) => (
        <Tag>{tokens.toLocaleString()}</Tag>
      )
    },
    {
      title: 'Mode',
      dataIndex: 'mode',
      key: 'mode',
      width: 100,
      render: (mode) => (
        <Tag color={mode === 'json' ? 'blue' : 'green'}>
          {mode?.toUpperCase() || 'TEXT'}
        </Tag>
      )
    },
    {
      title: 'Status',
      dataIndex: 'active',
      key: 'active',
      width: 100,
      render: (active) => (
        <Tag color={active ? 'green' : 'default'} icon={active ? <CheckCircleOutlined /> : null}>
          {active ? 'Active' : 'Inactive'}
        </Tag>
      ),
      sorter: (a, b) => a.active - b.active
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            onClick={() => navigate(`/llms/${record.id}/edit`)}
            size="small"
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete LLM Profile"
            description={`Are you sure you want to delete "${record.name}"?`}
            onConfirm={() => handleDelete(record)}
            okText="Yes"
            cancelText="No"
          >
            <Button danger icon={<DeleteOutlined />} size="small">
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const stats = {
    total: profiles.length,
    active: profiles.filter(p => p.active).length,
    openai: profiles.filter(p => p.endpoint?.includes('openai') || !p.endpoint).length,
    custom: profiles.filter(p => p.endpoint && !p.endpoint.includes('openai')).length
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <DatabaseOutlined style={{ fontSize: '24px' }} />
            <span>LLM Profiles</span>
            <Badge count={stats.total} style={{ backgroundColor: '#1890ff' }} />
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/llms/new')}
          >
            Create LLM Profile
          </Button>
        }
      >
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="Total Profiles"
                value={stats.total}
                prefix={<DatabaseOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="Active"
                value={stats.active}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="OpenAI"
                value={stats.openai}
                valueStyle={{ color: '#13c2c2' }}
                prefix={<ApiOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="Custom Endpoints"
                value={stats.custom}
                valueStyle={{ color: '#722ed1' }}
                prefix={<ApiOutlined />}
              />
            </Card>
          </Col>
        </Row>

        <Row style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Search
              placeholder="Search LLM profiles..."
              allowClear
              enterButton
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filteredProfiles}
          rowKey="id"
          loading={loading}
          pagination={{
            defaultPageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} profiles`,
          }}
          expandable={{
            expandedRowRender: (record) => (
              <div style={{ padding: '16px' }}>
                {record.system_prompt && (
                  <div style={{ marginBottom: '12px' }}>
                    <strong>System Prompt:</strong>
                    <div style={{ 
                      marginTop: '8px', 
                      padding: '12px', 
                      backgroundColor: '#f5f5f5',
                      borderRadius: '4px',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {record.system_prompt}
                    </div>
                  </div>
                )}
                {record.description && (
                  <div>
                    <strong>Description:</strong>
                    <div style={{ marginTop: '4px' }}>{record.description}</div>
                  </div>
                )}
                <div style={{ marginTop: '12px' }}>
                  <Space>
                    <Tag icon={<KeyOutlined />}>
                      API Key: {record.api_key ? '••••••' + record.api_key.slice(-4) : 'Not set'}
                    </Tag>
                    <Tag>
                      Created: {new Date(record.created_at).toLocaleDateString()}
                    </Tag>
                    <Tag>
                      Updated: {new Date(record.updated_at).toLocaleDateString()}
                    </Tag>
                  </Space>
                </div>
              </div>
            ),
            rowExpandable: (record) => record.system_prompt || record.description
          }}
        />
      </Card>
    </div>
  );
};

export default LLMProfileListAntd;