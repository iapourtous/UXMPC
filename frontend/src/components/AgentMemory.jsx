import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Space,
  Input,
  message,
  Popconfirm,
  Tag,
  Typography,
  Row,
  Col,
  Statistic,
  Empty,
  Spin,
  Tooltip,
  Badge,
  Modal,
  List,
  Divider,
  Timeline
} from 'antd';
import {
  DatabaseOutlined,
  SearchOutlined,
  DeleteOutlined,
  ClearOutlined,
  ReloadOutlined,
  HistoryOutlined,
  ArrowLeftOutlined,
  InfoCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
  RobotOutlined
} from '@ant-design/icons';
import { agentsApi, agentMemoryApi } from '../services/api';
import { format, formatDistanceToNow, parseISO } from 'date-fns';

const { Search } = Input;
const { Title, Text, Paragraph } = Typography;

const AgentMemory = () => {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [selectedMemory, setSelectedMemory] = useState(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);

  useEffect(() => {
    fetchAgent();
    fetchMemories();
    fetchStats();
  }, [agentId]);

  const fetchAgent = async () => {
    try {
      const response = await agentsApi.get(agentId);
      setAgent(response.data);
    } catch (error) {
      message.error('Failed to fetch agent details');
      navigate('/agents');
    }
  };

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const response = await agentMemoryApi.list(agentId, { limit: 100 });
      setMemories(response.data);
    } catch (error) {
      message.error('Failed to fetch memories');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await agentMemoryApi.stats(agentId);
      const data = response.data;
      // Transform the response to match our expected format
      setStats({
        total_memories: data.memory_summary?.total_memories || 0,
        conversation_count: data.memory_summary?.content_type_counts?.conversation || 0,
        avg_importance: data.memory_summary?.avg_importance || 0
      });
    } catch (error) {
      console.error('Failed to fetch memory stats');
    }
  };

  const handleSearch = async (query) => {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }

    setSearchLoading(true);
    try {
      const response = await agentMemoryApi.search(agentId, query, 10);
      setSearchResults(response.data);
    } catch (error) {
      message.error('Search failed');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleDelete = async (memoryId) => {
    try {
      await agentMemoryApi.delete(agentId, memoryId);
      message.success('Memory deleted');
      fetchMemories();
      fetchStats();
    } catch (error) {
      message.error('Failed to delete memory');
    }
  };

  const handleClearAll = async () => {
    try {
      await agentMemoryApi.clear(agentId);
      message.success('All memories cleared');
      setMemories([]);
      setSearchResults(null);
      fetchStats();
    } catch (error) {
      message.error('Failed to clear memories');
    }
  };

  const showMemoryDetail = (memory) => {
    setSelectedMemory(memory);
    setDetailModalVisible(true);
  };

  const getContentPreview = (content, maxLength = 100) => {
    if (!content) return '';
    const text = typeof content === 'string' ? content : JSON.stringify(content);
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const renderConversation = (content) => {
    try {
      const messages = JSON.parse(content);
      if (Array.isArray(messages)) {
        return (
          <Timeline>
            {messages.map((msg, index) => (
              <Timeline.Item
                key={index}
                color={msg.role === 'user' ? 'blue' : 'green'}
                dot={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Tag color={msg.role === 'user' ? 'blue' : 'green'}>
                    {msg.role.toUpperCase()}
                  </Tag>
                  <Paragraph
                    style={{ 
                      background: msg.role === 'user' ? '#f0f5ff' : '#f6ffed',
                      padding: '12px',
                      borderRadius: '8px',
                      margin: 0
                    }}
                  >
                    {msg.content}
                  </Paragraph>
                </Space>
              </Timeline.Item>
            ))}
          </Timeline>
        );
      }
    } catch (e) {
      // If not JSON, display as text
    }
    return <Paragraph>{content}</Paragraph>;
  };

  const columns = [
    {
      title: 'Type',
      dataIndex: 'content_type',
      key: 'content_type',
      width: 120,
      render: (type) => (
        <Tag color={type === 'conversation' ? 'blue' : 'green'}>
          {type}
        </Tag>
      ),
      filters: [
        { text: 'Conversation', value: 'conversation' },
        { text: 'Summary', value: 'summary' },
        { text: 'Preference', value: 'preference' },
      ],
      onFilter: (value, record) => record.content_type === value,
    },
    {
      title: 'Content',
      dataIndex: 'content',
      key: 'content',
      render: (content, record) => (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Text>{getContentPreview(content, 150)}</Text>
          <Space>
            <Button
              type="link"
              size="small"
              onClick={() => showMemoryDetail(record)}
            >
              View Full Content
            </Button>
            {record.metadata?.conversation_id && (
              <Tag color="purple">
                <HistoryOutlined /> {record.metadata.conversation_id.substring(0, 8)}...
              </Tag>
            )}
          </Space>
        </Space>
      ),
    },
    {
      title: 'Importance',
      dataIndex: 'importance',
      key: 'importance',
      width: 120,
      render: (importance) => (
        <Badge
          count={importance ? importance.toFixed(2) : '0.00'}
          style={{ backgroundColor: importance > 0.7 ? '#f5222d' : '#1890ff' }}
        />
      ),
      sorter: (a, b) => (a.importance || 0) - (b.importance || 0),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date) => (
        <Tooltip title={format(parseISO(date), 'yyyy-MM-dd HH:mm:ss')}>
          <Space>
            <ClockCircleOutlined />
            {formatDistanceToNow(parseISO(date), { addSuffix: true })}
          </Space>
        </Tooltip>
      ),
      sorter: (a, b) => new Date(a.created_at) - new Date(b.created_at),
      defaultSortOrder: 'descend',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title="Delete this memory?"
          description="This action cannot be undone."
          onConfirm={() => handleDelete(record.id)}
          okText="Delete"
          cancelText="Cancel"
        >
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            size="small"
          >
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const searchColumns = [
    ...columns.slice(0, -1), // All columns except actions
    {
      title: 'Relevance',
      dataIndex: 'score',
      key: 'score',
      width: 120,
      render: (score) => (
        <Badge
          count={score ? (score * 100).toFixed(0) + '%' : '0%'}
          style={{ backgroundColor: score > 0.7 ? '#52c41a' : '#1890ff' }}
        />
      ),
      sorter: (a, b) => (a.score || 0) - (b.score || 0),
      defaultSortOrder: 'descend',
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/agents')}
            >
              Back
            </Button>
            <DatabaseOutlined style={{ fontSize: '24px' }} />
            <span>Memory Management - {agent?.name}</span>
          </Space>
        }
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                fetchMemories();
                fetchStats();
              }}
            >
              Refresh
            </Button>
            <Popconfirm
              title="Clear all memories?"
              description="This will permanently delete all memories for this agent."
              onConfirm={handleClearAll}
              okText="Clear All"
              okButtonProps={{ danger: true }}
              cancelText="Cancel"
            >
              <Button danger icon={<ClearOutlined />}>
                Clear All
              </Button>
            </Popconfirm>
          </Space>
        }
      >
        {agent?.memory_enabled ? (
          <>
            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Total Memories"
                    value={stats?.total_memories || 0}
                    prefix={<DatabaseOutlined />}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Conversations"
                    value={stats?.conversation_count || 0}
                    prefix={<HistoryOutlined />}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Average Importance"
                    value={(stats?.avg_importance || 0).toFixed(2)}
                    suffix="/ 1.0"
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Memory Usage"
                    value={`${((stats?.total_memories || 0) / (agent?.memory_config?.max_memories || 1000) * 100).toFixed(0)}%`}
                    suffix={`/ ${agent?.memory_config?.max_memories || 1000}`}
                  />
                </Card>
              </Col>
            </Row>

            <Card
              title="Search Memories"
              style={{ marginBottom: 16 }}
              styles={{ body: { padding: '16px' } }}
            >
              <Search
                placeholder="Search through agent's memories..."
                enterButton={<SearchOutlined />}
                size="large"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onSearch={handleSearch}
                loading={searchLoading}
                allowClear
                onClear={() => setSearchResults(null)}
              />
            </Card>

            {searchResults ? (
              <Card title={`Search Results (${searchResults.length})`}>
                <Table
                  columns={searchColumns}
                  dataSource={searchResults.map(result => ({
                    ...result.memory,
                    score: result.score
                  }))}
                  rowKey="id"
                  loading={searchLoading}
                  pagination={{
                    pageSize: 10,
                    showTotal: (total) => `Total ${total} results`,
                  }}
                />
              </Card>
            ) : (
              <Card title="All Memories">
                <Table
                  columns={columns}
                  dataSource={memories}
                  rowKey="id"
                  loading={loading}
                  pagination={{
                    defaultPageSize: 20,
                    showSizeChanger: true,
                    showTotal: (total) => `Total ${total} memories`,
                  }}
                />
              </Card>
            )}
          </>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_DEFAULT}
            description={
              <Space direction="vertical">
                <Text>Memory is not enabled for this agent</Text>
                <Button
                  type="primary"
                  onClick={() => navigate(`/agents/${agentId}/edit`)}
                >
                  Enable Memory
                </Button>
              </Space>
            }
          />
        )}
      </Card>

      <Modal
        title="Memory Detail"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            Close
          </Button>,
        ]}
        width={800}
      >
        {selectedMemory && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Text strong>Type:</Text>
                <br />
                <Tag color="blue">{selectedMemory.content_type}</Tag>
              </Col>
              <Col span={12}>
                <Text strong>Importance:</Text>
                <br />
                <Badge
                  count={(selectedMemory.importance || 0).toFixed(2)}
                  style={{
                    backgroundColor:
                      selectedMemory.importance > 0.7 ? '#f5222d' : '#1890ff',
                  }}
                />
              </Col>
            </Row>

            <div>
              <Text strong>Created:</Text>
              <br />
              <Text>{format(parseISO(selectedMemory.created_at), 'yyyy-MM-dd HH:mm:ss')}</Text>
              <Text type="secondary"> ({formatDistanceToNow(parseISO(selectedMemory.created_at), { addSuffix: true })})</Text>
            </div>

            {selectedMemory.metadata && Object.keys(selectedMemory.metadata).length > 0 && (
              <div>
                <Text strong>Metadata:</Text>
                <br />
                <List
                  size="small"
                  dataSource={Object.entries(selectedMemory.metadata)}
                  renderItem={([key, value]) => (
                    <List.Item>
                      <Text code>{key}:</Text> {JSON.stringify(value)}
                    </List.Item>
                  )}
                />
              </div>
            )}

            <Divider />

            <div>
              <Text strong>Content:</Text>
              <div style={{ marginTop: 8 }}>
                {selectedMemory.content_type === 'conversation' ? (
                  renderConversation(selectedMemory.content)
                ) : (
                  <Paragraph
                    style={{
                      background: '#f5f5f5',
                      padding: '12px',
                      borderRadius: '8px',
                    }}
                  >
                    {selectedMemory.content}
                  </Paragraph>
                )}
              </div>
            </div>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default AgentMemory;