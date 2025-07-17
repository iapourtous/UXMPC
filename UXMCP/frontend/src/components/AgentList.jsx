import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Table, 
  Button, 
  message, 
  Space, 
  Tag, 
  Popconfirm,
  Input,
  Select,
  Card,
  Tooltip,
  Badge,
  Row,
  Col
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  PoweroffOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  RobotOutlined,
  ApiOutlined,
  ToolOutlined,
  BulbOutlined,
  DatabaseOutlined
} from '@ant-design/icons';
import { agentsApi } from '../services/api';

const { Search } = Input;
const { Option } = Select;

const AgentList = () => {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [filterActive, setFilterActive] = useState('all');

  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const response = await agentsApi.list();
      setAgents(response.data);
    } catch (error) {
      message.error('Failed to fetch agents');
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async (agent) => {
    try {
      await agentsApi.activate(agent.id);
      message.success(`Agent "${agent.name}" activated`);
      fetchAgents();
    } catch (error) {
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (detail.errors && detail.warnings) {
          message.error(
            <div>
              <div>{detail.message}</div>
              <div style={{ fontSize: '12px', marginTop: '4px' }}>
                Errors: {detail.errors.join(', ')}
              </div>
            </div>,
            5
          );
        } else {
          message.error(detail);
        }
      } else {
        message.error('Failed to activate agent');
      }
    }
  };

  const handleDeactivate = async (agent) => {
    try {
      await agentsApi.deactivate(agent.id);
      message.success(`Agent "${agent.name}" deactivated`);
      fetchAgents();
    } catch (error) {
      message.error('Failed to deactivate agent');
    }
  };

  const handleDelete = async (agent) => {
    try {
      await agentsApi.delete(agent.id);
      message.success(`Agent "${agent.name}" deleted`);
      fetchAgents();
    } catch (error) {
      message.error('Failed to delete agent');
    }
  };

  const handleTest = (agent) => {
    navigate(`/agents/${agent.id}/test`);
  };

  const filteredAgents = agents.filter(agent => {
    const matchesSearch = !searchText || 
      agent.name.toLowerCase().includes(searchText.toLowerCase()) ||
      agent.description?.toLowerCase().includes(searchText.toLowerCase()) ||
      agent.endpoint.toLowerCase().includes(searchText.toLowerCase());
    
    const matchesFilter = filterActive === 'all' || 
      (filterActive === 'active' && agent.active) ||
      (filterActive === 'inactive' && !agent.active);
    
    return matchesSearch && matchesFilter;
  });

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <RobotOutlined style={{ color: '#1890ff' }} />
          <strong>{text}</strong>
        </Space>
      )
    },
    {
      title: 'Endpoint',
      dataIndex: 'endpoint',
      key: 'endpoint',
      render: (text) => (
        <Tag icon={<ApiOutlined />} color="blue">
          {text}
        </Tag>
      )
    },
    {
      title: 'LLM Profile',
      dataIndex: 'llm_profile',
      key: 'llm_profile',
      render: (text) => <Tag color="purple">{text}</Tag>
    },
    {
      title: 'Services',
      dataIndex: 'mcp_services',
      key: 'mcp_services',
      render: (services) => (
        <Space size={[0, 4]} wrap>
          {services.length > 0 ? (
            <>
              <ToolOutlined />
              <Badge count={services.length} style={{ backgroundColor: '#52c41a' }} />
            </>
          ) : (
            <span style={{ color: '#999' }}>No services</span>
          )}
        </Space>
      )
    },
    {
      title: 'Features',
      key: 'features',
      render: (_, record) => (
        <Space>
          {record.memory_enabled && (
            <Tooltip title="Memory enabled">
              <Tag icon={<DatabaseOutlined />} color="blue">Memory</Tag>
            </Tooltip>
          )}
          {record.reasoning_strategy && record.reasoning_strategy !== 'standard' && (
            <Tooltip title={`Reasoning: ${record.reasoning_strategy}`}>
              <Tag icon={<BulbOutlined />} color="purple">{record.reasoning_strategy}</Tag>
            </Tooltip>
          )}
          {record.backstory && (
            <Tooltip title="Has backstory">
              <Tag color="gold">Identity</Tag>
            </Tooltip>
          )}
        </Space>
      )
    },
    {
      title: 'I/O Schema',
      key: 'schema',
      render: (_, record) => (
        <Space>
          <Tooltip title={`Input: ${typeof record.input_schema === 'string' ? record.input_schema : 'JSON'}`}>
            <Tag color="cyan">
              {typeof record.input_schema === 'string' ? record.input_schema : 'JSON'}
            </Tag>
          </Tooltip>
          <span>→</span>
          <Tooltip title={`Output: ${typeof record.output_schema === 'string' ? record.output_schema : 'JSON'}`}>
            <Tag color="orange">
              {typeof record.output_schema === 'string' ? record.output_schema : 'JSON'}
            </Tag>
          </Tooltip>
        </Space>
      )
    },
    {
      title: 'Status',
      dataIndex: 'active',
      key: 'active',
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
            type="link"
            icon={<EditOutlined />}
            onClick={() => navigate(`/agents/${record.id}/edit`)}
          >
            Edit
          </Button>
          {record.memory_enabled && (
            <Button
              type="link"
              icon={<DatabaseOutlined />}
              onClick={() => navigate(`/agents/${record.id}/memory`)}
            >
              Memory
            </Button>
          )}
          {record.active ? (
            <>
              <Button
                type="link"
                icon={<PlayCircleOutlined />}
                onClick={() => handleTest(record)}
              >
                Test
              </Button>
              <Button
                type="link"
                danger
                icon={<PoweroffOutlined />}
                onClick={() => handleDeactivate(record)}
              >
                Deactivate
              </Button>
            </>
          ) : (
            <Button
              type="link"
              icon={<CheckCircleOutlined />}
              onClick={() => handleActivate(record)}
              style={{ color: '#52c41a' }}
            >
              Activate
            </Button>
          )}
          <Popconfirm
            title="Delete Agent"
            description="Are you sure you want to delete this agent?"
            onConfirm={() => handleDelete(record)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card 
        title={
          <Space>
            <RobotOutlined style={{ fontSize: '24px' }} />
            <span>Agents</span>
            <Badge count={agents.length} style={{ backgroundColor: '#1890ff' }} />
          </Space>
        }
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/agents/new')}
            >
              Create Agent
            </Button>
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={() => navigate('/agents/create-meta')}
              style={{ backgroundColor: '#722ed1', borderColor: '#722ed1' }}
            >
              AI Agent Creator
            </Button>
          </Space>
        }
      >
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Search
              placeholder="Search agents by name, description, or endpoint"
              allowClear
              enterButton={<SearchOutlined />}
              size="large"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </Col>
          <Col>
            <Select
              value={filterActive}
              onChange={setFilterActive}
              style={{ width: 150 }}
              size="large"
            >
              <Option value="all">All Agents</Option>
              <Option value="active">Active Only</Option>
              <Option value="inactive">Inactive Only</Option>
            </Select>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filteredAgents}
          rowKey="id"
          loading={loading}
          pagination={{
            defaultPageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} agents`,
          }}
        />
      </Card>
    </div>
  );
};

export default AgentList;