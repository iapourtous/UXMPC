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
  Input
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  PoweroffOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  ApiOutlined,
  ToolOutlined,
  FileTextOutlined,
  MessageOutlined,
  BugOutlined,
  EyeOutlined,
  RobotOutlined
} from '@ant-design/icons';
import { servicesApi } from '../services/api';
import ServiceLogs from './ServiceLogs';
import TestResultModalAntd from './TestResultModalAntd';

const { Search } = Input;

const ServiceListAntd = () => {
  const navigate = useNavigate();
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [testResults, setTestResults] = useState(null);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [testingServiceId, setTestingServiceId] = useState(null);
  const [logsService, setLogsService] = useState(null);

  useEffect(() => {
    fetchServices();
  }, []);

  const fetchServices = async () => {
    setLoading(true);
    try {
      const response = await servicesApi.list();
      setServices(response.data);
    } catch (error) {
      message.error('Failed to fetch services');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (service) => {
    try {
      if (service.active) {
        await servicesApi.deactivate(service.id);
        message.success(`Service "${service.name}" deactivated`);
      } else {
        await servicesApi.activate(service.id);
        message.success(`Service "${service.name}" activated`);
      }
      fetchServices();
    } catch (error) {
      message.error(`Failed to ${service.active ? 'deactivate' : 'activate'} service`);
    }
  };

  const handleDelete = async (service) => {
    try {
      await servicesApi.delete(service.id);
      message.success(`Service "${service.name}" deleted`);
      fetchServices();
    } catch (error) {
      message.error('Failed to delete service');
    }
  };

  const handleTest = async (service) => {
    setTestingServiceId(service.id);
    try {
      const response = await fetch(`http://localhost:8000/services/${service.id}/test`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Test failed');
      }
      
      const result = await response.json();
      setTestResults(result);
      setIsTestModalOpen(true);
    } catch (error) {
      message.error(error.message || 'Failed to test service');
    } finally {
      setTestingServiceId(null);
    }
  };

  const getServiceTypeIcon = (type) => {
    switch (type) {
      case 'tool':
        return <ToolOutlined style={{ color: '#fa8c16' }} />;
      case 'resource':
        return <FileTextOutlined style={{ color: '#1890ff' }} />;
      case 'prompt':
        return <MessageOutlined style={{ color: '#52c41a' }} />;
      default:
        return <ApiOutlined />;
    }
  };

  const getServiceTypeColor = (type) => {
    switch (type) {
      case 'tool':
        return 'orange';
      case 'resource':
        return 'blue';
      case 'prompt':
        return 'green';
      default:
        return 'default';
    }
  };

  const filteredServices = services.filter(service =>
    !searchText || 
    service.name.toLowerCase().includes(searchText.toLowerCase()) ||
    service.description?.toLowerCase().includes(searchText.toLowerCase()) ||
    service.route.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          {getServiceTypeIcon(record.service_type)}
          <strong>{text}</strong>
        </Space>
      )
    },
    {
      title: 'Type',
      dataIndex: 'service_type',
      key: 'service_type',
      render: (type) => (
        <Tag color={getServiceTypeColor(type)} icon={getServiceTypeIcon(type)}>
          {type?.toUpperCase() || 'UNKNOWN'}
        </Tag>
      )
    },
    {
      title: 'Route',
      dataIndex: 'route',
      key: 'route',
      render: (route) => (
        <Tag icon={<ApiOutlined />} color="blue">
          {route}
        </Tag>
      )
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      render: (method) => (
        <Tag color="geekblue">{method}</Tag>
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
            type={record.active ? 'default' : 'primary'}
            danger={record.active}
            icon={record.active ? <PoweroffOutlined /> : <CheckCircleOutlined />}
            onClick={() => handleToggle(record)}
            size="small"
          >
            {record.active ? 'Deactivate' : 'Activate'}
          </Button>
          <Button
            icon={<EditOutlined />}
            onClick={() => navigate(`/services/${record.id}/edit`)}
            size="small"
          >
            Edit
          </Button>
          {record.llm_profile && (
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => handleTest(record)}
              loading={testingServiceId === record.id}
              size="small"
            >
              Test
            </Button>
          )}
          <Button
            icon={<BugOutlined />}
            onClick={() => setLogsService(record)}
            size="small"
          >
            Logs
          </Button>
          <Popconfirm
            title="Delete Service"
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
    total: services.length,
    active: services.filter(s => s.active).length,
    tools: services.filter(s => s.service_type === 'tool').length,
    resources: services.filter(s => s.service_type === 'resource').length,
    prompts: services.filter(s => s.service_type === 'prompt').length
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <ApiOutlined style={{ fontSize: '24px' }} />
            <span>MCP Services</span>
            <Badge count={stats.total} style={{ backgroundColor: '#1890ff' }} />
          </Space>
        }
        extra={
          <Space>
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={() => navigate('/services/create-ai')}
              style={{ background: '#722ed1', borderColor: '#722ed1' }}
            >
              Create with AI
            </Button>
            <Button
              icon={<PlusOutlined />}
              onClick={() => navigate('/services/new')}
            >
              Create Manually
            </Button>
          </Space>
        }
      >
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col span={4}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.total}</div>
                <div style={{ color: '#999' }}>Total Services</div>
              </div>
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>{stats.active}</div>
                <div style={{ color: '#999' }}>Active</div>
              </div>
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fa8c16' }}>{stats.tools}</div>
                <div style={{ color: '#999' }}>Tools</div>
              </div>
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>{stats.resources}</div>
                <div style={{ color: '#999' }}>Resources</div>
              </div>
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>{stats.prompts}</div>
                <div style={{ color: '#999' }}>Prompts</div>
              </div>
            </Card>
          </Col>
        </Row>

        <Row style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Search
              placeholder="Search services..."
              allowClear
              enterButton
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filteredServices}
          rowKey="id"
          loading={loading}
          pagination={{
            defaultPageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} services`,
          }}
        />
      </Card>

      {/* Test Results Modal */}
      {isTestModalOpen && testResults && (
        <TestResultModalAntd
          results={testResults}
          onClose={() => {
            setIsTestModalOpen(false);
            setTestResults(null);
          }}
        />
      )}

      {/* Logs Modal */}
      {logsService && (
        <ServiceLogs
          serviceId={logsService.id}
          serviceName={logsService.name}
          onClose={() => setLogsService(null)}
        />
      )}
    </div>
  );
};

export default ServiceListAntd;