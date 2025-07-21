import React, { useState, useEffect } from 'react';
import { Card, Button, Space, message, Popconfirm, Input, Typography, Modal, Form, Row, Col, Empty } from 'antd';
import { DeleteOutlined, EyeOutlined, SearchOutlined, EditOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { demosApi } from '../services/api';
import './DemoList.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const DemoList = () => {
  const [demos, setDemos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [searchQuery, setSearchQuery] = useState('');
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedDemo, setSelectedDemo] = useState(null);
  const [editForm] = Form.useForm();

  useEffect(() => {
    fetchDemos();
  }, [currentPage, pageSize]);

  const fetchDemos = async (search = '') => {
    setLoading(true);
    try {
      const response = await demosApi.list({
        skip: (currentPage - 1) * pageSize,
        limit: pageSize,
        search: search || undefined
      });
      
      setDemos(response.data.demos);
      setTotal(response.data.total);
    } catch (error) {
      message.error('Failed to fetch demos');
      console.error('Error fetching demos:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await demosApi.delete(id);
      message.success('Demo deleted successfully');
      fetchDemos(searchQuery);
    } catch (error) {
      message.error('Failed to delete demo');
      console.error('Error deleting demo:', error);
    }
  };

  const handleSearch = (value) => {
    setSearchQuery(value);
    setCurrentPage(1);
    fetchDemos(value);
  };

  const openDemo = (name) => {
    // Open the backend URL directly to get the HTML
    window.open(`${API_URL}/demos/${name}`, '_blank');
  };

  const handleEdit = (demo) => {
    setSelectedDemo(demo);
    editForm.setFieldsValue({
      description: demo.description
    });
    setEditModalVisible(true);
  };

  const handleUpdate = async () => {
    try {
      const values = await editForm.validateFields();
      await demosApi.update(selectedDemo.id, values);
      message.success('Demo updated successfully');
      setEditModalVisible(false);
      fetchDemos(searchQuery);
    } catch (error) {
      message.error('Failed to update demo');
      console.error('Error updating demo:', error);
    }
  };

  const handleShowDetails = (demo) => {
    setSelectedDemo(demo);
    setDetailModalVisible(true);
  };


  return (
    <div className="demo-list-container">
      <div className="demo-list-header">
        <Title level={2}>Interactive Demos</Title>
        <div className="demo-list-actions">
          <Input.Search
            placeholder="Search demos..."
            allowClear
            enterButton={<SearchOutlined />}
            size="large"
            onSearch={handleSearch}
            style={{ width: 300 }}
          />
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Card loading={loading} />
        </div>
      ) : demos.length === 0 ? (
        <Empty
          description="No demos found"
          style={{ marginTop: '50px' }}
        />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {demos.map((demo) => (
              <Col key={demo.id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  hoverable
                  title={demo.name}
                  extra={
                    <Button
                      type="primary"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => openDemo(demo.name)}
                    >
                      Open
                    </Button>
                  }
                  actions={[
                    <Button
                      key="edit"
                      type="text"
                      icon={<EditOutlined />}
                      onClick={() => handleEdit(demo)}
                    >
                      Edit
                    </Button>,
                    <Button
                      key="details"
                      type="text"
                      icon={<InfoCircleOutlined />}
                      onClick={() => handleShowDetails(demo)}
                    >
                      Details
                    </Button>,
                    <Popconfirm
                      key="delete"
                      title="Delete this demo?"
                      description="This action cannot be undone."
                      onConfirm={() => handleDelete(demo.id)}
                      okText="Yes"
                      cancelText="No"
                    >
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                      >
                        Delete
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <Paragraph ellipsis={{ rows: 3 }}>
                    {demo.description}
                  </Paragraph>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    Created: {new Date(demo.created_at).toLocaleDateString()}
                  </Text>
                </Card>
              </Col>
            ))}
          </Row>
          
          <div style={{ marginTop: '24px', textAlign: 'center' }}>
            <Space>
              <Button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(currentPage - 1)}
              >
                Previous
              </Button>
              <Text>
                Page {currentPage} of {Math.ceil(total / pageSize)} ({total} demos)
              </Text>
              <Button
                disabled={currentPage >= Math.ceil(total / pageSize)}
                onClick={() => setCurrentPage(currentPage + 1)}
              >
                Next
              </Button>
            </Space>
          </div>
        </>
      )}

      {/* Edit Modal */}
      <Modal
        title="Edit Demo"
        visible={editModalVisible}
        onOk={handleUpdate}
        onCancel={() => setEditModalVisible(false)}
        okText="Save"
      >
        <Form
          form={editForm}
          layout="vertical"
        >
          <Form.Item
            label="Description"
            name="description"
            rules={[
              { required: true, message: 'Please enter a description' },
              { max: 200, message: 'Description must be less than 200 characters' }
            ]}
          >
            <TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Details Modal */}
      <Modal
        title="Demo Details"
        visible={detailModalVisible}
        onOk={() => setDetailModalVisible(false)}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            Close
          </Button>
        ]}
        width={600}
      >
        {selectedDemo && (
          <div>
            <div style={{ marginBottom: '16px' }}>
              <Text strong>Name: </Text>
              <Text>{selectedDemo.name}</Text>
            </div>
            <div style={{ marginBottom: '16px' }}>
              <Text strong>Description: </Text>
              <Paragraph>{selectedDemo.description}</Paragraph>
            </div>
            <div style={{ marginBottom: '16px' }}>
              <Text strong>Original Query: </Text>
              <Paragraph>{selectedDemo.query}</Paragraph>
            </div>
            {selectedDemo.instructions && (
              <div style={{ marginBottom: '16px' }}>
                <Text strong>Custom Instructions: </Text>
                <Paragraph>{selectedDemo.instructions}</Paragraph>
              </div>
            )}
            <div style={{ marginBottom: '16px' }}>
              <Text strong>Created: </Text>
              <Text>{new Date(selectedDemo.created_at).toLocaleString()}</Text>
            </div>
            <div>
              <Text strong>URL: </Text>
              <Text copyable>{`${API_URL}/demos/${selectedDemo.name}`}</Text>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default DemoList;