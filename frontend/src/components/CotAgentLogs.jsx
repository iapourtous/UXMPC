import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
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
  Empty,
  Tabs,
  Collapse,
  Progress,
  Timeline,
  Space,
  Descriptions
} from 'antd';
import {
  BugOutlined,
  InfoCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  FireOutlined,
  ReloadOutlined,
  SearchOutlined,
  RobotOutlined,
  BulbOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  ExperimentOutlined
} from '@ant-design/icons';
import { format } from 'date-fns';

const { Option } = Select;
const { Search } = Input;
const { TabPane } = Tabs;
const { Panel } = Collapse;

const LOG_LEVELS = {
  DEBUG: { color: 'default', icon: <BugOutlined /> },
  INFO: { color: 'blue', icon: <InfoCircleOutlined /> },
  WARNING: { color: 'warning', icon: <WarningOutlined /> },
  ERROR: { color: 'error', icon: <CloseCircleOutlined /> },
  CRITICAL: { color: 'magenta', icon: <FireOutlined /> }
};

const CotAgentLogs = ({ agentId = null }) => {
  const [activeTab, setActiveTab] = useState(agentId ? 'agent' : 'cot');
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    level: 'ALL',
    search: '',
    limit: 100,
    executionId: null
  });
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [expandedRows, setExpandedRows] = useState([]);
  const [stats, setStats] = useState({
    totalLogs: 0,
    iterations: 0,
    toolCalls: 0,
    avgConfidence: 0
  });

  useEffect(() => {
    fetchLogs();
  }, [activeTab, filters, agentId]);

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchLogs();
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, activeTab, filters]);

  const fetchLogs = async () => {
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

      if (filters.executionId) {
        params.append('execution_id', filters.executionId);
      }

      let url;
      if (activeTab === 'cot') {
        url = `/logs/cot?${params}`;
      } else {
        url = `/logs/agents/${agentId}?${params}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch logs');

      const data = await response.json();
      setLogs(data);
      calculateStats(data);
    } catch (error) {
      message.error('Failed to fetch logs');
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (logsData) => {
    const iterations = logsData.filter(log => 
      log.details?.iteration_number !== undefined
    ).length;

    const toolCalls = logsData.filter(log => 
      log.details?.tool_name !== undefined
    ).length;

    const confidenceScores = logsData
      .filter(log => log.details?.confidence !== undefined)
      .map(log => log.details.confidence);

    const avgConfidence = confidenceScores.length > 0
      ? confidenceScores.reduce((a, b) => a + b, 0) / confidenceScores.length
      : 0;

    setStats({
      totalLogs: logsData.length,
      iterations,
      toolCalls,
      avgConfidence
    });
  };

  const renderLogDetails = (details) => {
    if (!details) return null;

    // Special rendering for COT iterations
    if (details.iteration_number !== undefined) {
      return (
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="Iteration">{details.iteration_number}</Descriptions.Item>
          <Descriptions.Item label="Reasoning Type">{details.reasoning_type}</Descriptions.Item>
          <Descriptions.Item label="Confidence">
            <Progress percent={Math.round(details.confidence * 100)} size="small" />
          </Descriptions.Item>
          <Descriptions.Item label="Should Continue">
            <Tag color={details.should_continue ? 'green' : 'orange'}>
              {details.should_continue ? 'Yes' : 'No'}
            </Tag>
          </Descriptions.Item>
          {details.thought && (
            <Descriptions.Item label="Thought" span={2}>
              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                {details.thought}
              </div>
            </Descriptions.Item>
          )}
          {details.tool_calls_count > 0 && (
            <Descriptions.Item label="Tool Calls">{details.tool_calls_count}</Descriptions.Item>
          )}
          {details.validation_scores && (
            <Descriptions.Item label="Validation Scores" span={2}>
              <Space>
                <Badge status="processing" text={`Relevance: ${details.validation_scores.relevance?.toFixed(2)}`} />
                <Badge status="processing" text={`Progress: ${details.validation_scores.progress?.toFixed(2)}`} />
                <Badge status="processing" text={`Correctness: ${details.validation_scores.correctness?.toFixed(2)}`} />
              </Space>
            </Descriptions.Item>
          )}
        </Descriptions>
      );
    }

    // Special rendering for tool execution
    if (details.tool_name) {
      return (
        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="Tool Name">
            <Tag icon={<ToolOutlined />}>{details.tool_name}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Success">
            {details.success ? (
              <Tag color="success" icon={<CheckCircleOutlined />}>Success</Tag>
            ) : (
              <Tag color="error" icon={<CloseCircleOutlined />}>Failed</Tag>
            )}
          </Descriptions.Item>
          {details.execution_time && (
            <Descriptions.Item label="Execution Time">
              {details.execution_time.toFixed(2)}ms
            </Descriptions.Item>
          )}
          {details.arguments && (
            <Descriptions.Item label="Arguments" span={2}>
              <pre style={{ maxHeight: 150, overflow: 'auto' }}>
                {JSON.stringify(details.arguments, null, 2)}
              </pre>
            </Descriptions.Item>
          )}
          {details.error && (
            <Descriptions.Item label="Error" span={2}>
              <Tag color="error">{details.error}</Tag>
            </Descriptions.Item>
          )}
        </Descriptions>
      );
    }

    // Default rendering for other details
    return (
      <pre style={{ maxHeight: 300, overflow: 'auto' }}>
        {JSON.stringify(details, null, 2)}
      </pre>
    );
  };

  const columns = [
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp) => (
        <Tooltip title={timestamp}>
          {format(new Date(timestamp), 'HH:mm:ss.SSS')}
        </Tooltip>
      ),
    },
    {
      title: 'Level',
      dataIndex: 'level',
      key: 'level',
      width: 100,
      render: (level) => (
        <Tag color={LOG_LEVELS[level]?.color} icon={LOG_LEVELS[level]?.icon}>
          {level}
        </Tag>
      ),
    },
    {
      title: 'Message',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
      render: (message, record) => {
        // Add icons based on message content
        let icon = null;
        if (message.includes('COT')) {
          icon = <BulbOutlined style={{ marginRight: 8, color: '#1890ff' }} />;
        } else if (message.includes('Tool')) {
          icon = <ToolOutlined style={{ marginRight: 8, color: '#52c41a' }} />;
        } else if (message.includes('Agent')) {
          icon = <RobotOutlined style={{ marginRight: 8, color: '#722ed1' }} />;
        }
        
        return (
          <span>
            {icon}
            {message}
          </span>
        );
      },
    },
    {
      title: 'Details',
      key: 'details',
      width: 100,
      render: (_, record) => (
        record.details && Object.keys(record.details).length > 0 ? (
          <Button
            size="small"
            onClick={() => {
              if (expandedRows.includes(record.id)) {
                setExpandedRows(expandedRows.filter(id => id !== record.id));
              } else {
                setExpandedRows([...expandedRows, record.id]);
              }
            }}
          >
            {expandedRows.includes(record.id) ? 'Hide' : 'Show'}
          </Button>
        ) : null
      ),
    },
  ];

  const renderIterationTimeline = () => {
    const iterations = logs.filter(log => log.details?.iteration_number !== undefined);
    if (iterations.length === 0) return <Empty description="No iterations found" />;

    return (
      <Timeline mode="left">
        {iterations.map((log, index) => (
          <Timeline.Item
            key={log.id}
            color={log.details.confidence > 0.8 ? 'green' : log.details.confidence > 0.5 ? 'blue' : 'orange'}
            dot={<ExperimentOutlined />}
          >
            <Card size="small">
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title={`Iteration ${log.details.iteration_number}`}
                    value={log.details.reasoning_type}
                    prefix={<BulbOutlined />}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Confidence"
                    value={`${(log.details.confidence * 100).toFixed(1)}%`}
                    valueStyle={{ color: log.details.confidence > 0.7 ? '#3f8600' : '#cf1322' }}
                  />
                </Col>
              </Row>
              {log.details.thought && (
                <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
                  {log.details.thought.substring(0, 150)}...
                </div>
              )}
            </Card>
          </Timeline.Item>
        ))}
      </Timeline>
    );
  };

  return (
    <Card
      title={
        <Row justify="space-between" align="middle">
          <Col>
            <Space>
              {activeTab === 'cot' ? <BulbOutlined /> : <RobotOutlined />}
              <span>{activeTab === 'cot' ? 'Chain of Thought Logs' : 'Agent Execution Logs'}</span>
            </Space>
          </Col>
          <Col>
            <Space>
              <Tooltip title="Auto-refresh">
                <Switch
                  checked={autoRefresh}
                  onChange={setAutoRefresh}
                  checkedChildren={<SyncOutlined spin />}
                  unCheckedChildren={<SyncOutlined />}
                />
              </Tooltip>
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchLogs}
                loading={loading}
              >
                Refresh
              </Button>
            </Space>
          </Col>
        </Row>
      }
    >
      {!agentId && (
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="Chain of Thought" key="cot" />
          <TabPane tab="Agent Logs" key="agent" disabled={!agentId} />
        </Tabs>
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Statistic
            title="Total Logs"
            value={stats.totalLogs}
            prefix={<InfoCircleOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="Iterations"
            value={stats.iterations}
            prefix={<BrainOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="Tool Calls"
            value={stats.toolCalls}
            prefix={<ToolOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="Avg Confidence"
            value={`${(stats.avgConfidence * 100).toFixed(1)}%`}
            prefix={<ExperimentOutlined />}
          />
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Select
            style={{ width: '100%' }}
            placeholder="Filter by level"
            value={filters.level}
            onChange={(value) => setFilters({ ...filters, level: value })}
          >
            <Option value="ALL">All Levels</Option>
            <Option value="DEBUG">Debug</Option>
            <Option value="INFO">Info</Option>
            <Option value="WARNING">Warning</Option>
            <Option value="ERROR">Error</Option>
            <Option value="CRITICAL">Critical</Option>
          </Select>
        </Col>
        <Col span={6}>
          <Input
            placeholder="Execution ID"
            value={filters.executionId}
            onChange={(e) => setFilters({ ...filters, executionId: e.target.value })}
            allowClear
          />
        </Col>
        <Col span={12}>
          <Search
            placeholder="Search logs..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            onSearch={fetchLogs}
            allowClear
          />
        </Col>
      </Row>

      <Tabs defaultActiveKey="table">
        <TabPane tab="Table View" key="table">
          <Table
            columns={columns}
            dataSource={logs}
            loading={loading}
            rowKey="id"
            size="small"
            pagination={{
              pageSize: 50,
              showSizeChanger: true,
              showTotal: (total) => `Total ${total} logs`,
            }}
            expandable={{
              expandedRowRender: (record) => renderLogDetails(record.details),
              expandedRowKeys: expandedRows,
              onExpandedRowsChange: setExpandedRows,
              rowExpandable: (record) => record.details && Object.keys(record.details).length > 0,
            }}
          />
        </TabPane>
        <TabPane tab="Timeline View" key="timeline">
          {renderIterationTimeline()}
        </TabPane>
      </Tabs>
    </Card>
  );
};

export default CotAgentLogs;