import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Space, Tag,
  message, Tooltip, Row, Col, Statistic, Switch, InputNumber,
  Descriptions, Divider, Empty, Typography, Badge, Alert
} from 'antd';
import {
  FolderOutlined, PlusOutlined, EditOutlined, DeleteOutlined,
  UserOutlined, LockOutlined, UnlockOutlined, TeamOutlined,
  FileOutlined, DatabaseOutlined, SettingOutlined, ReloadOutlined
} from '@ant-design/icons';
import { workspacesApi, agentsApi } from '../services/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const WorkspaceManager = () => {
  const [workspaces, setWorkspaces] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState(null);
  const [selectedWorkspace, setSelectedWorkspace] = useState(null);
  const [workspaceStats, setWorkspaceStats] = useState(null);
  const [form] = Form.useForm();
  const [agentModalVisible, setAgentModalVisible] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState([]);

  useEffect(() => {
    loadWorkspaces();
    loadAgents();
  }, []);

  const loadWorkspaces = async () => {
    setLoading(true);
    try {
      const response = await workspacesApi.list();
      setWorkspaces(response.data || []);
    } catch (error) {
      message.error('Failed to load workspaces');
      console.error('Error loading workspaces:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const response = await agentsApi.list();
      setAgents(response.data || []);
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  };

  const loadWorkspaceStats = async (workspaceId) => {
    try {
      const response = await workspacesApi.getStats(workspaceId);
      setWorkspaceStats(response.data);
    } catch (error) {
      console.error('Error loading workspace stats:', error);
    }
  };

  const handleCreate = () => {
    setEditingWorkspace(null);
    form.resetFields();
    form.setFieldsValue({
      settings: {
        max_file_size: 52428800,
        auto_extract: true,
        auto_embed: true,
      }
    });
    setModalVisible(true);
  };

  const handleEdit = (workspace) => {
    setEditingWorkspace(workspace);
    form.setFieldsValue(workspace);
    setModalVisible(true);
  };

  const handleDelete = (workspace) => {
    Modal.confirm({
      title: 'Delete Workspace',
      content: (
        <>
          <p>Are you sure you want to delete "{workspace.name}"?</p>
          {workspace.document_count > 0 && (
            <Alert
              message={`This workspace contains ${workspace.document_count} documents that must be deleted first.`}
              type="warning"
              showIcon
            />
          )}
        </>
      ),
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await workspacesApi.delete(workspace.id);
          message.success('Workspace deleted successfully');
          loadWorkspaces();
        } catch (error) {
          message.error(error.response?.data?.detail || 'Failed to delete workspace');
          console.error('Error deleting workspace:', error);
        }
      }
    });
  };

  const handleSubmit = async (values) => {
    try {
      if (editingWorkspace) {
        await workspacesApi.update(editingWorkspace.id, values);
        message.success('Workspace updated successfully');
      } else {
        await workspacesApi.create(values);
        message.success('Workspace created successfully');
      }
      setModalVisible(false);
      loadWorkspaces();
    } catch (error) {
      message.error(error.response?.data?.detail || 'Operation failed');
      console.error('Error saving workspace:', error);
    }
  };

  const handleManageAgents = (workspace) => {
    setSelectedWorkspace(workspace);
    setSelectedAgents(workspace.agent_ids || []);
    setAgentModalVisible(true);
  };

  const handleUpdateAgents = async () => {
    if (!selectedWorkspace) return;

    try {
      // Get current agents
      const currentAgents = selectedWorkspace.agent_ids || [];
      
      // Find agents to add and remove
      const toAdd = selectedAgents.filter(id => !currentAgents.includes(id));
      const toRemove = currentAgents.filter(id => !selectedAgents.includes(id));

      // Add new agents
      for (const agentId of toAdd) {
        await workspacesApi.addAgent(selectedWorkspace.id, agentId);
      }

      // Remove agents
      for (const agentId of toRemove) {
        await workspacesApi.removeAgent(selectedWorkspace.id, agentId);
      }

      message.success('Agent access updated successfully');
      setAgentModalVisible(false);
      loadWorkspaces();
    } catch (error) {
      message.error('Failed to update agent access');
      console.error('Error updating agents:', error);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <FolderOutlined />
          <Text strong>{text}</Text>
          {record.is_public && (
            <Tag color="green" icon={<UnlockOutlined />}>Public</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Documents',
      dataIndex: 'document_count',
      key: 'document_count',
      width: 100,
      render: (count) => (
        <Badge count={count} showZero>
          <FileOutlined style={{ fontSize: 16 }} />
        </Badge>
      ),
    },
    {
      title: 'Size',
      dataIndex: 'total_size',
      key: 'total_size',
      width: 120,
      render: formatFileSize,
    },
    {
      title: 'Agents',
      dataIndex: 'agent_ids',
      key: 'agent_ids',
      width: 150,
      render: (agentIds) => (
        <Space>
          <TeamOutlined />
          <Text>{agentIds?.length || 0} agents</Text>
        </Space>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (date) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space>
          <Tooltip title="View Details">
            <Button
              icon={<SettingOutlined />}
              size="small"
              onClick={() => {
                setSelectedWorkspace(record);
                loadWorkspaceStats(record.id);
              }}
            />
          </Tooltip>
          <Tooltip title="Manage Agents">
            <Button
              icon={<TeamOutlined />}
              size="small"
              onClick={() => handleManageAgents(record)}
            />
          </Tooltip>
          <Tooltip title="Edit">
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Tooltip title="Delete">
            <Button
              icon={<DeleteOutlined />}
              size="small"
              danger
              disabled={record.document_count > 0}
              onClick={() => handleDelete(record)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Row gutter={[16, 16]} align="middle" style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Title level={3}>
              <FolderOutlined /> Workspace Management
            </Title>
          </Col>
          <Col>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={loadWorkspaces}
              >
                Refresh
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreate}
              >
                Create Workspace
              </Button>
            </Space>
          </Col>
        </Row>

        {/* Workspaces Table */}
        <Table
          columns={columns}
          dataSource={workspaces}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} workspaces`,
          }}
          locale={{
            emptyText: (
              <Empty
                description="No workspaces found"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={handleCreate}
                >
                  Create First Workspace
                </Button>
              </Empty>
            )
          }}
        />

        {/* Selected Workspace Details */}
        {selectedWorkspace && workspaceStats && (
          <Card style={{ marginTop: 16 }} title={`Workspace: ${selectedWorkspace.name}`}>
            <Row gutter={[16, 16]}>
              <Col span={6}>
                <Statistic
                  title="Total Documents"
                  value={workspaceStats.document_count}
                  prefix={<FileOutlined />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="Total Size"
                  value={formatFileSize(workspaceStats.total_size)}
                  prefix={<DatabaseOutlined />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="Document Types"
                  value={Object.keys(workspaceStats.document_types || {}).length}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="Agents with Access"
                  value={selectedWorkspace.agent_ids?.length || 0}
                  prefix={<TeamOutlined />}
                />
              </Col>
            </Row>

            <Divider />

            <Descriptions bordered size="small">
              <Descriptions.Item label="Description" span={3}>
                {selectedWorkspace.description || 'No description'}
              </Descriptions.Item>
              <Descriptions.Item label="Visibility">
                {selectedWorkspace.is_public ? (
                  <Tag color="green" icon={<UnlockOutlined />}>Public</Tag>
                ) : (
                  <Tag color="red" icon={<LockOutlined />}>Private</Tag>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Max File Size">
                {formatFileSize(selectedWorkspace.settings?.max_file_size || 52428800)}
              </Descriptions.Item>
              <Descriptions.Item label="Auto Extract">
                {selectedWorkspace.settings?.auto_extract ? 'Yes' : 'No'}
              </Descriptions.Item>
              <Descriptions.Item label="Created">
                {new Date(selectedWorkspace.created_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="Updated">
                {new Date(selectedWorkspace.updated_at).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>

            {workspaceStats.recent_uploads?.length > 0 && (
              <>
                <Divider>Recent Uploads</Divider>
                <Table
                  size="small"
                  columns={[
                    { title: 'Name', dataIndex: 'name', key: 'name' },
                    { title: 'Type', dataIndex: 'type', key: 'type' },
                    {
                      title: 'Created',
                      dataIndex: 'created_at',
                      key: 'created_at',
                      render: (date) => new Date(date).toLocaleDateString()
                    }
                  ]}
                  dataSource={workspaceStats.recent_uploads}
                  rowKey="id"
                  pagination={false}
                />
              </>
            )}
          </Card>
        )}
      </Card>

      {/* Create/Edit Modal */}
      <Modal
        title={editingWorkspace ? 'Edit Workspace' : 'Create Workspace'}
        visible={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="Workspace Name"
            rules={[{ required: true, message: 'Please enter workspace name' }]}
          >
            <Input placeholder="Enter workspace name" />
          </Form.Item>

          <Form.Item
            name="description"
            label="Description"
          >
            <TextArea
              rows={3}
              placeholder="Enter workspace description (optional)"
            />
          </Form.Item>

          <Form.Item
            name="is_public"
            label="Visibility"
            initialValue={false}
          >
            <Select>
              <Option value={false}>
                <LockOutlined /> Private - Only assigned agents can access
              </Option>
              <Option value={true}>
                <UnlockOutlined /> Public - All agents can access
              </Option>
            </Select>
          </Form.Item>

          <Divider>Settings</Divider>

          <Form.Item
            name={['settings', 'max_file_size']}
            label="Maximum File Size (bytes)"
            initialValue={52428800}
          >
            <InputNumber
              min={1048576}
              max={524288000}
              step={1048576}
              style={{ width: '100%' }}
              formatter={value => `${formatFileSize(value)}`}
              parser={value => value.replace(/[^\d]/g, '')}
            />
          </Form.Item>

          <Form.Item
            name={['settings', 'auto_extract']}
            label="Auto Extract Content"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="Yes" unCheckedChildren="No" />
          </Form.Item>

          <Form.Item
            name={['settings', 'auto_embed']}
            label="Auto Generate Embeddings"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="Yes" unCheckedChildren="No" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                {editingWorkspace ? 'Update' : 'Create'}
              </Button>
              <Button onClick={() => setModalVisible(false)}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Agent Management Modal */}
      <Modal
        title={`Manage Agent Access: ${selectedWorkspace?.name}`}
        visible={agentModalVisible}
        onCancel={() => setAgentModalVisible(false)}
        onOk={handleUpdateAgents}
        width={600}
      >
        <Alert
          message="Select agents that should have access to this workspace"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="Select agents"
          value={selectedAgents}
          onChange={setSelectedAgents}
          optionFilterProp="children"
          filterOption={(input, option) =>
            option.children.toLowerCase().includes(input.toLowerCase())
          }
        >
          {agents.map(agent => (
            <Option key={agent.id} value={agent.id}>
              <Space>
                <UserOutlined />
                {agent.name}
                {agent.active && <Tag color="green">Active</Tag>}
              </Space>
            </Option>
          ))}
        </Select>

        {selectedAgents.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Text strong>Selected Agents ({selectedAgents.length}):</Text>
            <div style={{ marginTop: 8 }}>
              {selectedAgents.map(agentId => {
                const agent = agents.find(a => a.id === agentId);
                return agent ? (
                  <Tag key={agentId} closable onClose={() => {
                    setSelectedAgents(selectedAgents.filter(id => id !== agentId));
                  }}>
                    {agent.name}
                  </Tag>
                ) : null;
              })}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default WorkspaceManager;