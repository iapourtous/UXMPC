import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Space,
  Switch,
  message,
  Tabs,
  Row,
  Col,
  Alert,
  Tag,
  Tooltip,
  Divider,
  Table
} from 'antd';
import {
  SaveOutlined,
  CloseOutlined,
  ApiOutlined,
  CodeOutlined,
  PlusOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  MessageOutlined
} from '@ant-design/icons';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { json } from '@codemirror/lang-json';
import { servicesApi, llmApi } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { TabPane } = Tabs;

const ServiceFormAntd = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [serviceType, setServiceType] = useState('tool');
  const [params, setParams] = useState([]);

  useEffect(() => {
    fetchLLMProfiles();
    if (id) {
      fetchService();
    }
  }, [id]);

  const fetchLLMProfiles = async () => {
    try {
      const response = await llmApi.list(true);
      setLlmProfiles(response.data);
    } catch (error) {
      message.error('Failed to fetch LLM profiles');
    }
  };

  const fetchService = async () => {
    setLoading(true);
    try {
      const response = await servicesApi.get(id);
      const service = response.data;
      
      setServiceType(service.service_type);
      setParams(service.params || []);
      
      form.setFieldsValue({
        ...service,
        dependencies: service.dependencies?.join(', ') || '',
        prompt_args: service.prompt_args || []
      });
    } catch (error) {
      message.error('Failed to fetch service');
      navigate('/services');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const processedValues = {
        ...values,
        params,
        dependencies: values.dependencies
          ? values.dependencies.split(',').map(d => d.trim()).filter(Boolean)
          : [],
        prompt_args: serviceType === 'prompt' ? values.prompt_args || [] : []
      };

      if (id) {
        await servicesApi.update(id, processedValues);
        message.success('Service updated successfully');
      } else {
        await servicesApi.create(processedValues);
        message.success('Service created successfully');
      }
      navigate('/services');
    } catch (error) {
      message.error(id ? 'Failed to update service' : 'Failed to create service');
    } finally {
      setLoading(false);
    }
  };

  const handleAddParam = () => {
    setParams([...params, { name: '', type: 'string', required: true, description: '' }]);
  };

  const handleRemoveParam = (index) => {
    setParams(params.filter((_, i) => i !== index));
  };

  const handleParamChange = (index, field, value) => {
    const newParams = [...params];
    newParams[index][field] = value;
    setParams(newParams);
  };

  const paramColumns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (_, record, index) => (
        <Input
          value={record.name}
          onChange={(e) => handleParamChange(index, 'name', e.target.value)}
          placeholder="param_name"
        />
      )
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (_, record, index) => (
        <Select
          value={record.type}
          onChange={(value) => handleParamChange(index, 'type', value)}
          style={{ width: '100%' }}
        >
          <Option value="string">String</Option>
          <Option value="number">Number</Option>
          <Option value="boolean">Boolean</Option>
          <Option value="object">Object</Option>
          <Option value="array">Array</Option>
        </Select>
      )
    },
    {
      title: 'Required',
      dataIndex: 'required',
      key: 'required',
      width: 100,
      render: (_, record, index) => (
        <Switch
          checked={record.required}
          onChange={(checked) => handleParamChange(index, 'required', checked)}
        />
      )
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (_, record, index) => (
        <Input
          value={record.description}
          onChange={(e) => handleParamChange(index, 'description', e.target.value)}
          placeholder="Parameter description"
        />
      )
    },
    {
      title: 'Action',
      key: 'action',
      width: 80,
      render: (_, record, index) => (
        <Button
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleRemoveParam(index)}
          size="small"
        />
      )
    }
  ];

  const defaultCode = {
    tool: `def handler(**params):
    # Access parameters
    param_value = params.get('param_name', 'default_value')
    
    # Your tool logic here
    result = {
        "status": "success",
        "data": f"Processed: {param_value}"
    }
    
    return result`,
    resource: `def handler(**params):
    # Resource handler returns data
    data = {
        "title": "Resource Title",
        "content": "Resource content here",
        "metadata": {
            "created": datetime.datetime.utcnow().isoformat()
        }
    }
    
    return data`,
    prompt: `def handler(**params):
    # Access prompt arguments
    context = params.get('context', '')
    
    # Build the prompt
    prompt = f"""
You are a helpful assistant.

Context: {context}

Please provide assistance based on the above context.
"""
    
    return {"prompt": prompt}`
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <ApiOutlined style={{ fontSize: '24px' }} />
            <span>{id ? 'Edit Service' : 'Create Service'}</span>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            service_type: 'tool',
            method: 'GET',
            active: false,
            code: defaultCode.tool
          }}
        >
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="Service Name"
                rules={[
                  { required: true, message: 'Please enter service name' },
                  { pattern: /^[a-zA-Z0-9_-]+$/, message: 'Only alphanumeric, underscore and hyphen allowed' }
                ]}
              >
                <Input
                  prefix={<ApiOutlined />}
                  placeholder="my_service"
                  disabled={!!id}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="service_type"
                label="Service Type"
                rules={[{ required: true }]}
              >
                <Select
                  onChange={setServiceType}
                  disabled={!!id}
                >
                  <Option value="tool">
                    <Space>
                      <Tag color="orange">Tool</Tag>
                      <span>Callable function</span>
                    </Space>
                  </Option>
                  <Option value="resource">
                    <Space>
                      <Tag color="blue">Resource</Tag>
                      <span>Data provider</span>
                    </Space>
                  </Option>
                  <Option value="prompt">
                    <Space>
                      <Tag color="green">Prompt</Tag>
                      <span>Template generator</span>
                    </Space>
                  </Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={24}>
            <Col span={16}>
              <Form.Item
                name="route"
                label="API Route"
                rules={[
                  { required: true, message: 'Please enter route' },
                  { pattern: /^\//, message: 'Route must start with /' }
                ]}
                extra="Use {param} for path parameters"
              >
                <Input
                  prefix={<ApiOutlined />}
                  placeholder="/api/my-service/{param}"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="method"
                label="HTTP Method"
                rules={[{ required: true }]}
              >
                <Select>
                  <Option value="GET">GET</Option>
                  <Option value="POST">POST</Option>
                  <Option value="PUT">PUT</Option>
                  <Option value="DELETE">DELETE</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="description"
            label="Description"
          >
            <TextArea
              rows={2}
              placeholder="Describe what this service does..."
            />
          </Form.Item>

          <Divider />

          <Tabs defaultActiveKey="code">
            <TabPane tab={<span><CodeOutlined /> Code</span>} key="code">
              <Form.Item
                name="code"
                label="Handler Function"
                rules={[{ required: true, message: 'Please enter handler code' }]}
                extra="Define a handler(**params) function that returns a dictionary"
                getValueFromEvent={(value) => value}
                getValueProps={(value) => ({
                  value: value || ''
                })}
              >
                <CodeMirror
                  height="400px"
                  extensions={[python()]}
                  theme="light"
                />
              </Form.Item>

              <Form.Item
                name="dependencies"
                label="Python Dependencies"
                extra="Comma-separated list of modules to import (e.g., requests, datetime)"
              >
                <Input placeholder="requests, datetime, json" />
              </Form.Item>
            </TabPane>

            <TabPane tab={<span><FileTextOutlined /> Parameters</span>} key="params">
              <div style={{ marginBottom: 16 }}>
                <Button
                  type="dashed"
                  onClick={handleAddParam}
                  icon={<PlusOutlined />}
                  block
                >
                  Add Parameter
                </Button>
              </div>
              
              <Table
                columns={paramColumns}
                dataSource={params}
                rowKey={(record, index) => index}
                pagination={false}
                size="small"
              />
            </TabPane>

            {serviceType === 'prompt' && (
              <TabPane tab={<span><MessageOutlined /> Prompt Config</span>} key="prompt">
                <Form.Item
                  name="prompt_template"
                  label="Prompt Template"
                  extra="Use {arg_name} for arguments"
                >
                  <TextArea
                    rows={6}
                    placeholder="You are a helpful assistant. {context}"
                  />
                </Form.Item>
              </TabPane>
            )}

            <TabPane tab={<span><InfoCircleOutlined /> Advanced</span>} key="advanced">
              <Form.Item
                name="llm_profile"
                label={
                  <Space>
                    LLM Profile
                    <Tooltip title="Required for AI-powered testing">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </Space>
                }
              >
                <Select
                  placeholder="Select LLM profile for testing"
                  allowClear
                  showSearch
                  optionFilterProp="children"
                >
                  {llmProfiles.map(profile => (
                    <Option key={profile.name} value={profile.name}>
                      <Space>
                        <Tag color="purple">{profile.model}</Tag>
                        {profile.name}
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                name="documentation"
                label="Documentation"
              >
                <TextArea
                  rows={4}
                  placeholder="Detailed documentation for this service..."
                />
              </Form.Item>

              <Row gutter={24}>
                <Col span={12}>
                  <Form.Item
                    name="input_schema"
                    label="Input Schema (JSON)"
                    getValueFromEvent={(value) => value}
                    getValueProps={(value) => ({
                      value: typeof value === 'object' ? JSON.stringify(value, null, 2) : value || ''
                    })}
                  >
                    <CodeMirror
                      height="200px"
                      extensions={[json()]}
                      placeholder='{"type": "object", "properties": {...}}'
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="output_schema"
                    label="Output Schema (JSON)"
                    getValueFromEvent={(value) => value}
                    getValueProps={(value) => ({
                      value: typeof value === 'object' ? JSON.stringify(value, null, 2) : value || ''
                    })}
                  >
                    <CodeMirror
                      height="200px"
                      extensions={[json()]}
                      placeholder='{"type": "object", "properties": {...}}'
                    />
                  </Form.Item>
                </Col>
              </Row>
            </TabPane>
          </Tabs>

          <Divider />

          {!id && (
            <Alert
              message="Note"
              description="After creating the service, you'll need to activate it to make it available."
              type="info"
              showIcon
              style={{ marginBottom: 24 }}
            />
          )}

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<SaveOutlined />}
              >
                {id ? 'Update Service' : 'Create Service'}
              </Button>
              <Button
                onClick={() => navigate('/services')}
                icon={<CloseOutlined />}
              >
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default ServiceFormAntd;