import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
  Space,
  Select,
  Input,
  Button,
  Badge,
  Row,
  Col,
  Statistic,
  Divider,
  message,
  Switch,
  Tooltip,
  Empty
} from 'antd';
import {
  FileSearchOutlined,
  ReloadOutlined,
  DownloadOutlined,
  FilterOutlined,
  ClockCircleOutlined,
  InfoCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  FireOutlined,
  BugOutlined,
  BarChartOutlined,
  SearchOutlined
} from '@ant-design/icons';
import { format } from 'date-fns';
import { servicesApi } from '../services/api';

const { Option } = Select;
const { Search } = Input;

const LOG_LEVELS = {
  DEBUG: { color: 'default', icon: <BugOutlined /> },
  INFO: { color: 'blue', icon: <InfoCircleOutlined /> },
  WARNING: { color: 'warning', icon: <WarningOutlined /> },
  ERROR: { color: 'error', icon: <CloseCircleOutlined /> },
  CRITICAL: { color: 'magenta', icon: <FireOutlined /> }
};

const LogsView = () => {
  const [services, setServices] = useState([]);
  const [selectedService, setSelectedService] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [filters, setFilters] = useState({
    level: 'ALL',
    search: '',
    limit: 100
  });
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [expandedRows, setExpandedRows] = useState([]);

  useEffect(() => {
    fetchServices();
  }, []);

  useEffect(() => {
    if (selectedService) {
      fetchLogs();
      fetchStats();
    }
  }, [selectedService, filters]);

  useEffect(() => {
    let interval;
    if (autoRefresh && selectedService) {
      interval = setInterval(() => {
        fetchLogs();
        fetchStats();
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, selectedService]);

  const fetchServices = async () => {
    try {
      const response = await servicesApi.list();
      setServices(response.data);
    } catch (error) {
      message.error('Failed to fetch services');
    }
  };

  const fetchLogs = async () => {
    if (!selectedService) return;
    
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: filters.limit
      });
      
      if (filters.level !== 'ALL') {
        params.append('level', filters.level);
      }
      
      if (filters.search) {
        params.append('search', filters.search);
      }

      const response = await fetch(`http://localhost:8000/logs/services/${selectedService}?${params}`);
      if (!response.ok) throw new Error('Failed to fetch logs');
      
      const data = await response.json();
      setLogs(data);
    } catch (error) {
      message.error('Failed to fetch logs');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    if (!selectedService) return;
    
    try {
      const response = await fetch(`http://localhost:8000/logs/services/stats/${selectedService}?hours=24`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const handleServiceChange = (serviceId) => {
    setSelectedService(serviceId);
    setLogs([]);
    setStats(null);
  };

  const handleExport = () => {
    if (!logs || logs.length === 0) {
      message.warning('No logs to export');
      return;
    }

    const content = JSON.stringify(logs, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${selectedService}-${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    message.success('Logs exported successfully');
  };

  const clearOldLogs = async () => {
    if (!selectedService) return;
    
    const days = 7;
    if (!window.confirm(`Delete logs older than ${days} days?`)) return;
    
    try {
      const response = await fetch(`http://localhost:8000/logs/services/${selectedService}/old?days=${days}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) throw new Error('Failed to delete logs');
      
      const result = await response.json();
      message.success(result.message);
      fetchLogs();
      fetchStats();
    } catch (error) {
      message.error('Failed to delete logs');
    }
  };

  const columns = [
    {
      title: 'Time',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp) => (
        <Tooltip title={format(new Date(timestamp), 'yyyy-MM-dd HH:mm:ss.SSS')}>
          <span className="font-mono text-xs">
            {format(new Date(timestamp), 'HH:mm:ss.SSS')}
          </span>
        </Tooltip>
      )
    },
    {
      title: 'Level',
      dataIndex: 'level',
      key: 'level',
      width: 100,
      render: (level) => (
        <Tag color={LOG_LEVELS[level].color} icon={LOG_LEVELS[level].icon}>
          {level}
        </Tag>
      )
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'message',
      render: (message, record) => (
        <div>
          <div>{message}</div>
          {record.details && Object.keys(record.details).length > 0 && (
            <Button
              type="link"
              size="small"
              onClick={() => {
                const newExpanded = expandedRows.includes(record.id)
                  ? expandedRows.filter(id => id !== record.id)
                  : [...expandedRows, record.id];
                setExpandedRows(newExpanded);
              }}
            >
              {expandedRows.includes(record.id) ? 'Hide' : 'Show'} details
            </Button>
          )}
        </div>
      )
    },
    {
      title: 'Execution',
      dataIndex: 'execution_id',
      key: 'execution_id',
      width: 150,
      render: (executionId) => executionId ? (
        <Tooltip title={executionId}>
          <span className="font-mono text-xs">
            {executionId.substring(0, 8)}...
          </span>
        </Tooltip>
      ) : '-'
    }
  ];

  const expandedRowRender = (record) => {
    if (!record.details || !expandedRows.includes(record.id)) return null;
    
    return (
      <div style={{ margin: 16 }}>
        <pre style={{ 
          backgroundColor: '#f5f5f5', 
          padding: 12, 
          borderRadius: 4,
          overflow: 'auto',
          maxHeight: 300
        }}>
          {JSON.stringify(record.details, null, 2)}
        </pre>
      </div>
    );
  };

  const selectedServiceData = services.find(s => s.id === selectedService);

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <FileSearchOutlined style={{ fontSize: '24px' }} />
            <span>Service Logs</span>
          </Space>
        }
      >
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Space size="large" style={{ width: '100%', justifyContent: 'space-between' }} wrap>
              <Select
                placeholder="Select a service"
                style={{ width: 300 }}
                onChange={handleServiceChange}
                value={selectedService}
                showSearch
                optionFilterProp="children"
              >
                {services.map(service => (
                  <Option key={service.id} value={service.id}>
                    {service.name} {service.active && <Tag color="green">Active</Tag>}
                  </Option>
                ))}
              </Select>

              <Space>
                <Switch
                  checkedChildren={<ReloadOutlined spin />}
                  unCheckedChildren={<ReloadOutlined />}
                  checked={autoRefresh}
                  onChange={setAutoRefresh}
                />
                <span>Auto-refresh</span>
              </Space>
            </Space>
          </Col>

          {selectedService && (
            <>
              {stats && (
                <Col span={24}>
                  <Row gutter={16}>
                    <Col span={4}>
                      <Card size="small">
                        <Statistic
                          title="Total Logs"
                          value={stats.total}
                          prefix={<BarChartOutlined />}
                        />
                      </Card>
                    </Col>
                    <Col span={4}>
                      <Card size="small">
                        <Statistic
                          title="Executions"
                          value={stats.executions}
                          prefix={<ClockCircleOutlined />}
                        />
                      </Card>
                    </Col>
                    {stats.error > 0 && (
                      <Col span={4}>
                        <Card size="small">
                          <Statistic
                            title="Errors"
                            value={stats.error}
                            prefix={<CloseCircleOutlined />}
                            valueStyle={{ color: '#cf1322' }}
                          />
                        </Card>
                      </Col>
                    )}
                    {stats.warning > 0 && (
                      <Col span={4}>
                        <Card size="small">
                          <Statistic
                            title="Warnings"
                            value={stats.warning}
                            prefix={<WarningOutlined />}
                            valueStyle={{ color: '#faad14' }}
                          />
                        </Card>
                      </Col>
                    )}
                  </Row>
                </Col>
              )}

              <Col span={24}>
                <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
                  <Space>
                    <Select
                      value={filters.level}
                      onChange={(value) => setFilters({ ...filters, level: value })}
                      style={{ width: 120 }}
                    >
                      <Option value="ALL">All Levels</Option>
                      {Object.keys(LOG_LEVELS).map(level => (
                        <Option key={level} value={level}>
                          <Space>
                            {LOG_LEVELS[level].icon}
                            {level}
                          </Space>
                        </Option>
                      ))}
                    </Select>

                    <Search
                      placeholder="Search logs..."
                      value={filters.search}
                      onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                      style={{ width: 300 }}
                      enterButton={<SearchOutlined />}
                    />

                    <Select
                      value={filters.limit}
                      onChange={(value) => setFilters({ ...filters, limit: value })}
                      style={{ width: 120 }}
                    >
                      <Option value={50}>Last 50</Option>
                      <Option value={100}>Last 100</Option>
                      <Option value={200}>Last 200</Option>
                      <Option value={500}>Last 500</Option>
                    </Select>
                  </Space>

                  <Space>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={fetchLogs}
                      loading={loading}
                    >
                      Refresh
                    </Button>
                    <Button
                      icon={<DownloadOutlined />}
                      onClick={handleExport}
                      disabled={logs.length === 0}
                    >
                      Export
                    </Button>
                    <Button
                      danger
                      onClick={clearOldLogs}
                    >
                      Clear Old Logs
                    </Button>
                  </Space>
                </Space>
              </Col>

              <Col span={24}>
                <Table
                  columns={columns}
                  dataSource={logs}
                  rowKey="id"
                  loading={loading}
                  expandable={{
                    expandedRowRender,
                    expandedRowKeys: expandedRows,
                    showExpandColumn: false
                  }}
                  pagination={{
                    defaultPageSize: 50,
                    showSizeChanger: true,
                    pageSizeOptions: ['20', '50', '100'],
                    showTotal: (total) => `Total ${total} logs`
                  }}
                  scroll={{ x: 800 }}
                  locale={{
                    emptyText: <Empty description="No logs found" />
                  }}
                />
              </Col>
            </>
          )}

          {!selectedService && (
            <Col span={24}>
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="Select a service to view its logs"
              />
            </Col>
          )}
        </Row>
      </Card>
    </div>
  );
};

export default LogsView;