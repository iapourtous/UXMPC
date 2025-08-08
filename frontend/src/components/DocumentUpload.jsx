import React, { useState } from 'react';
import {
  Upload, Button, Form, Input, Select, Tag, message, Progress,
  Card, Space, Alert, Divider
} from 'antd';
import {
  InboxOutlined, UploadOutlined, FileOutlined,
  DeleteOutlined, CheckCircleOutlined
} from '@ant-design/icons';
import { documentsApi } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { Dragger } = Upload;

const DocumentUpload = ({ workspaces, onSuccess }) => {
  const [form] = Form.useForm();
  const [fileList, setFileList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [tags, setTags] = useState([]);
  const [tagInput, setTagInput] = useState('');

  const documentTypes = [
    { value: 'pdf', label: 'PDF' },
    { value: 'text', label: 'Text' },
    { value: 'markdown', label: 'Markdown' },
    { value: 'html', label: 'HTML' },
    { value: 'json', label: 'JSON' },
    { value: 'csv', label: 'CSV' },
    { value: 'docx', label: 'DOCX' },
    { value: 'xlsx', label: 'XLSX' },
    { value: 'image', label: 'Image' },
    { value: 'other', label: 'Other' }
  ];

  const categories = [
    { value: 'documentation', label: 'Documentation' },
    { value: 'code', label: 'Code' },
    { value: 'data', label: 'Data' },
    { value: 'report', label: 'Report' },
    { value: 'presentation', label: 'Presentation' },
    { value: 'reference', label: 'Reference' },
    { value: 'manual', label: 'Manual' },
    { value: 'other', label: 'Other' }
  ];

  const detectDocumentType = (file) => {
    const extension = file.name.split('.').pop().toLowerCase();
    const mimeType = file.type;

    // Map extensions to document types
    const extensionMap = {
      'pdf': 'pdf',
      'txt': 'text',
      'md': 'markdown',
      'html': 'html',
      'htm': 'html',
      'json': 'json',
      'csv': 'csv',
      'docx': 'docx',
      'doc': 'docx',
      'xlsx': 'xlsx',
      'xls': 'xlsx',
      'png': 'image',
      'jpg': 'image',
      'jpeg': 'image',
      'gif': 'image',
      'bmp': 'image',
      'svg': 'image',
    };

    // Check by extension first
    if (extensionMap[extension]) {
      return extensionMap[extension];
    }

    // Check by MIME type
    if (mimeType) {
      if (mimeType.includes('pdf')) return 'pdf';
      if (mimeType.includes('text')) return 'text';
      if (mimeType.includes('json')) return 'json';
      if (mimeType.includes('csv')) return 'csv';
      if (mimeType.includes('image')) return 'image';
      if (mimeType.includes('html')) return 'html';
    }

    return 'other';
  };

  const uploadProps = {
    name: 'file',
    multiple: false,
    fileList,
    beforeUpload: (file) => {
      setFileList([file]);
      
      // Auto-detect document type
      const detectedType = detectDocumentType(file);
      form.setFieldsValue({
        name: file.name,
        type: detectedType
      });

      return false; // Prevent auto upload
    },
    onRemove: () => {
      setFileList([]);
      form.setFieldsValue({
        name: '',
        type: undefined
      });
    }
  };

  const handleAddTag = () => {
    if (tagInput && !tags.includes(tagInput)) {
      setTags([...tags, tagInput]);
      setTagInput('');
    }
  };

  const handleRemoveTag = (tagToRemove) => {
    setTags(tags.filter(tag => tag !== tagToRemove));
  };

  const handleUpload = async (values) => {
    if (fileList.length === 0) {
      message.error('Please select a file to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', fileList[0]);
    formData.append('name', values.name);
    formData.append('type', values.type);
    formData.append('workspace_id', values.workspace_id);
    formData.append('description', values.description || '');
    formData.append('category', values.category || 'other');
    formData.append('tags', tags.join(','));
    formData.append('is_public', values.is_public || false);

    try {
      // Upload with progress tracking
      const response = await documentsApi.create(formData);
      
      setUploadProgress(100);
      message.success('Document uploaded successfully');
      
      // Extract content automatically if possible
      if (response.data && response.data.id) {
        try {
          await documentsApi.extractContent(response.data.id);
          message.success('Content extracted and indexed');
        } catch (error) {
          console.log('Content extraction failed silently:', error);
        }
      }

      // Reset form
      form.resetFields();
      setFileList([]);
      setTags([]);
      setUploadProgress(0);

      if (onSuccess) {
        onSuccess(response.data);
      }
    } catch (error) {
      message.error('Failed to upload document');
      console.error('Upload error:', error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleUpload}
      >
        {/* File Upload */}
        <Form.Item
          label="Select File"
          required
        >
          <Dragger {...uploadProps}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">
              Click or drag file to this area to upload
            </p>
            <p className="ant-upload-hint">
              Support for PDF, Word, Excel, Text, Markdown, JSON, CSV, Images and more.
              Files up to 50MB are supported.
            </p>
          </Dragger>
        </Form.Item>

        {fileList.length > 0 && (
          <>
            <Alert
              message="File Selected"
              description={`${fileList[0].name} (${(fileList[0].size / 1024 / 1024).toFixed(2)} MB)`}
              type="success"
              showIcon
              icon={<CheckCircleOutlined />}
              style={{ marginBottom: 16 }}
            />

            <Divider />

            {/* Document Details */}
            <Form.Item
              name="workspace_id"
              label="Workspace"
              rules={[{ required: true, message: 'Please select a workspace' }]}
            >
              <Select placeholder="Select a workspace">
                {workspaces.map(ws => (
                  <Option key={ws.id} value={ws.id}>
                    {ws.name}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="name"
              label="Document Name"
              rules={[{ required: true, message: 'Please enter document name' }]}
            >
              <Input placeholder="Enter document name" />
            </Form.Item>

            <Form.Item
              name="type"
              label="Document Type"
              rules={[{ required: true, message: 'Please select document type' }]}
            >
              <Select placeholder="Select document type">
                {documentTypes.map(type => (
                  <Option key={type.value} value={type.value}>
                    {type.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="category"
              label="Category"
              initialValue="other"
            >
              <Select placeholder="Select category">
                {categories.map(cat => (
                  <Option key={cat.value} value={cat.value}>
                    {cat.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="description"
              label="Description"
            >
              <TextArea
                rows={3}
                placeholder="Enter document description (optional)"
              />
            </Form.Item>

            <Form.Item label="Tags">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space wrap>
                  {tags.map(tag => (
                    <Tag
                      key={tag}
                      closable
                      onClose={() => handleRemoveTag(tag)}
                    >
                      {tag}
                    </Tag>
                  ))}
                </Space>
                <Space>
                  <Input
                    placeholder="Add a tag"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onPressEnter={handleAddTag}
                    style={{ width: 200 }}
                  />
                  <Button onClick={handleAddTag}>Add Tag</Button>
                </Space>
              </Space>
            </Form.Item>

            <Form.Item
              name="is_public"
              label="Visibility"
              initialValue={false}
            >
              <Select>
                <Option value={false}>Private</Option>
                <Option value={true}>Public</Option>
              </Select>
            </Form.Item>
          </>
        )}

        {/* Upload Progress */}
        {uploading && (
          <Progress
            percent={uploadProgress}
            status={uploadProgress === 100 ? 'success' : 'active'}
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Submit Button */}
        <Form.Item>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              loading={uploading}
              disabled={fileList.length === 0}
              icon={<UploadOutlined />}
              size="large"
            >
              {uploading ? 'Uploading...' : 'Upload Document'}
            </Button>
            {fileList.length > 0 && !uploading && (
              <Button
                onClick={() => {
                  setFileList([]);
                  form.resetFields();
                  setTags([]);
                }}
                icon={<DeleteOutlined />}
              >
                Clear
              </Button>
            )}
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default DocumentUpload;