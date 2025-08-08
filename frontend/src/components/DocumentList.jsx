import React, { useState, useEffect } from 'react';
import {
  Table, Button, Space, Modal, message, Tag, Tooltip, Dropdown, Select,
  Input, Card, Row, Col, Statistic, Typography, Upload, Tabs, Badge,
  Descriptions, Divider, Empty, Spin, Progress
} from 'antd';
import {
  FileOutlined, DownloadOutlined, DeleteOutlined, EditOutlined,
  SearchOutlined, UploadOutlined, FolderOutlined, EyeOutlined,
  FileTextOutlined, FilePdfOutlined, FileExcelOutlined, FileImageOutlined,
  FileMarkdownOutlined, FileUnknownOutlined, ReloadOutlined, PlusOutlined
} from '@ant-design/icons';
import { documentsApi, workspacesApi } from '../services/api';
import DocumentUpload from './DocumentUpload';
import DocumentEdit from './DocumentEdit';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Search } = Input;
const { Option } = Select;

const DocumentList = () => {
  const [documents, setDocuments] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedWorkspace, setSelectedWorkspace] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedType, setSelectedType] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [documentContent, setDocumentContent] = useState('');
  const [workspaceStats, setWorkspaceStats] = useState(null);

  // Document type icons
  const getDocumentIcon = (type) => {
    const icons = {
      pdf: <FilePdfOutlined style={{ color: '#ff4d4f' }} />,
      text: <FileTextOutlined style={{ color: '#52c41a' }} />,
      markdown: <FileMarkdownOutlined style={{ color: '#1890ff' }} />,
      excel: <FileExcelOutlined style={{ color: '#52c41a' }} />,
      xlsx: <FileExcelOutlined style={{ color: '#52c41a' }} />,
      image: <FileImageOutlined style={{ color: '#fa8c16' }} />,
      json: <FileTextOutlined style={{ color: '#722ed1' }} />,
      csv: <FileExcelOutlined style={{ color: '#13c2c2' }} />,
    };
    return icons[type] || <FileUnknownOutlined />;
  };

  // Category colors
  const getCategoryColor = (category) => {
    const colors = {
      documentation: 'blue',
      code: 'green',
      data: 'orange',
      report: 'purple',
      presentation: 'cyan',
      reference: 'magenta',
      manual: 'gold',
      other: 'default'
    };
    return colors[category] || 'default';
  };

  useEffect(() => {
    loadWorkspaces();
    loadDocuments();
  }, []);

  useEffect(() => {
    loadDocuments();
    if (selectedWorkspace) {
      loadWorkspaceStats(selectedWorkspace);
    }
  }, [selectedWorkspace, selectedCategory, selectedType]);

  const loadWorkspaces = async () => {
    try {
      const response = await workspacesApi.list();
      setWorkspaces(response.data || []);
    } catch (error) {
      message.error('Failed to load workspaces');
      console.error('Error loading workspaces:', error);
    }
  };

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedWorkspace) params.workspace_id = selectedWorkspace;
      if (selectedCategory) params.category = selectedCategory;
      if (selectedType) params.type = selectedType;

      const response = await documentsApi.list(params);
      setDocuments(response.data || []);
    } catch (error) {
      message.error('Failed to load documents');
      console.error('Error loading documents:', error);
    } finally {
      setLoading(false);
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

  const handleDownload = async (document) => {
    try {
      const response = await documentsApi.download(document.id);
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = document.name;
      link.click();
      window.URL.revokeObjectURL(url);
      message.success('Document downloaded successfully');
    } catch (error) {
      message.error('Failed to download document');
      console.error('Error downloading document:', error);
    }
  };

  const handleDelete = async (document) => {
    Modal.confirm({
      title: 'Delete Document',
      content: `Are you sure you want to delete "${document.name}"?`,
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await documentsApi.delete(document.id);
          message.success('Document deleted successfully');
          loadDocuments();
          if (selectedWorkspace) {
            loadWorkspaceStats(selectedWorkspace);
          }
        } catch (error) {
          message.error('Failed to delete document');
          console.error('Error deleting document:', error);
        }
      }
    });
  };

  const handlePreview = async (document) => {
    setSelectedDocument(document);
    setPreviewModalVisible(true);
    setDocumentContent('Loading...');

    try {
      const response = await documentsApi.getContent(document.id);
      setDocumentContent(response.data.content || 'No content available');
    } catch (error) {
      setDocumentContent('Failed to load content');
      console.error('Error loading document content:', error);
    }
  };

  const handleExtractContent = async (document) => {
    try {
      message.loading('Extracting content...', 0);
      const response = await documentsApi.extractContent(document.id);
      message.destroy();
      message.success(`Content extracted: ${response.data.content_length} characters`);
      loadDocuments();
    } catch (error) {
      message.destroy();
      message.error('Failed to extract content');
      console.error('Error extracting content:', error);
    }
  };

  const handleEdit = (document) => {
    setSelectedDocument(document);
    setEditModalVisible(true);
  };

  const handleEditSuccess = (updatedDocument) => {
    // Update the document in the list
    setDocuments(prevDocs => 
      prevDocs.map(doc => 
        doc.id === updatedDocument.id ? updatedDocument : doc
      )
    );
    message.success('Document updated successfully');
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadDocuments();
      return;
    }

    setLoading(true);
    try {
      const searchParams = {
        query: searchQuery,
        workspace_ids: selectedWorkspace ? [selectedWorkspace] : [],
        use_semantic: true,
        limit: 50
      };

      const response = await documentsApi.search(searchParams);
      const searchResults = response.data.map(result => result.document);
      setDocuments(searchResults);
    } catch (error) {
      message.error('Search failed');
      console.error('Error searching documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '-';
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
          {getDocumentIcon(record.type)}
          <Text strong>{text}</Text>
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type) => <Tag>{type}</Tag>,
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (category) => (
        <Tag color={getCategoryColor(category)}>{category}</Tag>
      ),
    },
    {
      title: 'Size',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: formatFileSize,
    },
    {
      title: 'Tags',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags) => (
        <>
          {tags && tags.slice(0, 3).map(tag => (
            <Tag key={tag} style={{ marginBottom: 4 }}>{tag}</Tag>
          ))}
          {tags && tags.length > 3 && <Tag>+{tags.length - 3}</Tag>}
        </>
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
          <Tooltip title="Preview">
            <Button
              icon={<EyeOutlined />}
              size="small"
              onClick={() => handlePreview(record)}
            />
          </Tooltip>
          <Tooltip title="Edit">
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Tooltip title="Download">
            <Button
              icon={<DownloadOutlined />}
              size="small"
              onClick={() => handleDownload(record)}
            />
          </Tooltip>
          {!record.content && (
            <Tooltip title="Extract Content">
              <Button
                icon={<FileTextOutlined />}
                size="small"
                onClick={() => handleExtractContent(record)}
              />
            </Tooltip>
          )}
          <Tooltip title="Delete">
            <Button
              icon={<DeleteOutlined />}
              size="small"
              danger
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
          <Col span={24}>
            <Title level={3}>
              <FileOutlined /> Document Management
            </Title>
          </Col>
        </Row>

        {/* Filters */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={12} md={6}>
            <Select
              style={{ width: '100%' }}
              placeholder="Select Workspace"
              allowClear
              value={selectedWorkspace}
              onChange={setSelectedWorkspace}
            >
              {workspaces.map(ws => (
                <Option key={ws.id} value={ws.id}>
                  <FolderOutlined /> {ws.name}
                </Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="Category"
              allowClear
              value={selectedCategory}
              onChange={setSelectedCategory}
            >
              <Option value="documentation">Documentation</Option>
              <Option value="code">Code</Option>
              <Option value="data">Data</Option>
              <Option value="report">Report</Option>
              <Option value="presentation">Presentation</Option>
              <Option value="reference">Reference</Option>
              <Option value="manual">Manual</Option>
              <Option value="other">Other</Option>
            </Select>
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Select
              style={{ width: '100%' }}
              placeholder="Type"
              allowClear
              value={selectedType}
              onChange={setSelectedType}
            >
              <Option value="pdf">PDF</Option>
              <Option value="text">Text</Option>
              <Option value="markdown">Markdown</Option>
              <Option value="html">HTML</Option>
              <Option value="json">JSON</Option>
              <Option value="csv">CSV</Option>
              <Option value="docx">DOCX</Option>
              <Option value="xlsx">XLSX</Option>
              <Option value="image">Image</Option>
              <Option value="other">Other</Option>
            </Select>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Search
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onSearch={handleSearch}
              enterButton={<SearchOutlined />}
            />
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={loadDocuments}
              >
                Refresh
              </Button>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                onClick={() => setUploadModalVisible(true)}
              >
                Upload
              </Button>
            </Space>
          </Col>
        </Row>

        {/* Workspace Stats */}
        {workspaceStats && (
          <Card style={{ marginBottom: 16 }}>
            <Row gutter={16}>
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
                  prefix={<FolderOutlined />}
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
                  title="Categories"
                  value={Object.keys(workspaceStats.categories || {}).length}
                />
              </Col>
            </Row>
          </Card>
        )}

        {/* Documents Table */}
        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} documents`,
          }}
          locale={{
            emptyText: (
              <Empty
                description="No documents found"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  onClick={() => setUploadModalVisible(true)}
                >
                  Upload First Document
                </Button>
              </Empty>
            )
          }}
        />
      </Card>

      {/* Upload Modal */}
      <Modal
        title="Upload Documents"
        visible={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
        width={800}
      >
        <DocumentUpload
          workspaces={workspaces}
          onSuccess={() => {
            setUploadModalVisible(false);
            loadDocuments();
            if (selectedWorkspace) {
              loadWorkspaceStats(selectedWorkspace);
            }
          }}
        />
      </Modal>

      {/* Preview Modal */}
      <Modal
        title={selectedDocument ? `Preview: ${selectedDocument.name}` : 'Document Preview'}
        visible={previewModalVisible}
        onCancel={() => {
          setPreviewModalVisible(false);
          setSelectedDocument(null);
          setDocumentContent('');
        }}
        width={900}
        footer={[
          <Button key="close" onClick={() => setPreviewModalVisible(false)}>
            Close
          </Button>,
          selectedDocument && (
            <Button
              key="download"
              type="primary"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(selectedDocument)}
            >
              Download
            </Button>
          )
        ]}
      >
        {selectedDocument && (
          <>
            <Descriptions bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="Type">{selectedDocument.type}</Descriptions.Item>
              <Descriptions.Item label="Category">
                <Tag color={getCategoryColor(selectedDocument.category)}>
                  {selectedDocument.category}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Size">
                {formatFileSize(selectedDocument.file_size)}
              </Descriptions.Item>
              <Descriptions.Item label="Created">
                {new Date(selectedDocument.created_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="Access Count">
                {selectedDocument.access_count || 0}
              </Descriptions.Item>
              <Descriptions.Item label="Tags" span={3}>
                {selectedDocument.tags?.map(tag => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </Descriptions.Item>
              {selectedDocument.description && (
                <Descriptions.Item label="Description" span={3}>
                  {selectedDocument.description}
                </Descriptions.Item>
              )}
            </Descriptions>

            <Divider>Content</Divider>
            <div style={{
              maxHeight: 400,
              overflow: 'auto',
              padding: 16,
              backgroundColor: '#f5f5f5',
              borderRadius: 4,
            }}>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {documentContent}
              </pre>
            </div>
          </>
        )}
      </Modal>

      <DocumentEdit
        visible={editModalVisible}
        document={selectedDocument}
        onCancel={() => setEditModalVisible(false)}
        onSuccess={handleEditSuccess}
      />
    </div>
  );
};

export default DocumentList;