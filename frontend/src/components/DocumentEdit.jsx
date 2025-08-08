import React, { useState, useEffect } from 'react';
import {
  Modal, Form, Input, Select, Switch, message, Tag, Button, Space
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { documentsApi, workspacesApi } from '../services/api';

const { TextArea } = Input;
const { Option } = Select;

// Document categories
const DOCUMENT_CATEGORIES = [
  'documentation',
  'code', 
  'data',
  'report',
  'presentation',
  'reference',
  'manual',
  'other'
];

const DocumentEdit = ({ visible, document, onCancel, onSuccess }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [workspaces, setWorkspaces] = useState([]);
  const [tags, setTags] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [inputVisible, setInputVisible] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [keywordInputVisible, setKeywordInputVisible] = useState(false);
  const [keywordInputValue, setKeywordInputValue] = useState('');
  const [metadataEntries, setMetadataEntries] = useState([]);

  // Load workspaces on component mount
  useEffect(() => {
    const loadWorkspaces = async () => {
      try {
        const response = await workspacesApi.list();
        setWorkspaces(response.data || []);
      } catch (error) {
        console.error('Failed to load workspaces:', error);
        message.error('Failed to load workspaces');
      }
    };
    
    if (visible) {
      loadWorkspaces();
    }
  }, [visible]);

  // Initialize form when document changes
  useEffect(() => {
    if (document && visible) {
      const metadataArray = Object.entries(document.metadata || {}).map(([key, value]) => ({
        key,
        value: typeof value === 'object' ? JSON.stringify(value) : String(value),
        id: Math.random()
      }));

      form.setFieldsValue({
        description: document.description || '',
        workspace_id: document.workspace_id,
        category: document.category,
        is_public: document.is_public || false
      });

      setTags(document.tags || []);
      setKeywords(document.keywords || []);
      setMetadataEntries(metadataArray);
    }
  }, [document, visible, form]);

  const handleSubmit = async (values) => {
    try {
      setLoading(true);

      // Convert metadata entries back to object
      const metadata = {};
      metadataEntries.forEach(entry => {
        if (entry.key && entry.key.trim()) {
          try {
            // Try to parse as JSON first, fallback to string
            metadata[entry.key] = JSON.parse(entry.value);
          } catch {
            metadata[entry.key] = entry.value;
          }
        }
      });

      const updateData = {
        description: values.description || null,
        workspace_id: values.workspace_id,
        category: values.category,
        tags: tags,
        keywords: keywords,
        metadata: metadata,
        is_public: values.is_public || false
      };

      const response = await documentsApi.update(document.id, updateData);
      
      message.success('Document updated successfully');
      onSuccess(response.data);
      handleCancel();
      
    } catch (error) {
      console.error('Failed to update document:', error);
      message.error('Failed to update document: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    setTags([]);
    setKeywords([]);
    setMetadataEntries([]);
    setInputVisible(false);
    setInputValue('');
    setKeywordInputVisible(false);
    setKeywordInputValue('');
    onCancel();
  };

  // Tag management
  const handleTagClose = (removedTag) => {
    setTags(tags.filter(tag => tag !== removedTag));
  };

  const showTagInput = () => {
    setInputVisible(true);
  };

  const handleTagInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleTagInputConfirm = () => {
    if (inputValue && tags.indexOf(inputValue) === -1) {
      setTags([...tags, inputValue]);
    }
    setInputVisible(false);
    setInputValue('');
  };

  // Keywords management
  const handleKeywordClose = (removedKeyword) => {
    setKeywords(keywords.filter(kw => kw !== removedKeyword));
  };

  const showKeywordInput = () => {
    setKeywordInputVisible(true);
  };

  const handleKeywordInputChange = (e) => {
    setKeywordInputValue(e.target.value);
  };

  const handleKeywordInputConfirm = () => {
    if (keywordInputValue && keywords.indexOf(keywordInputValue) === -1) {
      setKeywords([...keywords, keywordInputValue]);
    }
    setKeywordInputVisible(false);
    setKeywordInputValue('');
  };

  // Metadata management
  const addMetadataEntry = () => {
    setMetadataEntries([...metadataEntries, { key: '', value: '', id: Math.random() }]);
  };

  const updateMetadataEntry = (id, field, value) => {
    setMetadataEntries(entries => 
      entries.map(entry => 
        entry.id === id ? { ...entry, [field]: value } : entry
      )
    );
  };

  const removeMetadataEntry = (id) => {
    setMetadataEntries(entries => entries.filter(entry => entry.id !== id));
  };

  if (!document) return null;

  return (
    <Modal
      title={`Edit Document: ${document.name}`}
      open={visible}
      onCancel={handleCancel}
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          Cancel
        </Button>,
        <Button 
          key="submit" 
          type="primary" 
          loading={loading}
          onClick={() => form.submit()}
        >
          Update Document
        </Button>
      ]}
      width={600}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
      >
        <Form.Item
          name="description"
          label="Description"
        >
          <TextArea 
            rows={3} 
            placeholder="Enter document description..."
          />
        </Form.Item>

        <Form.Item
          name="workspace_id"
          label="Workspace"
          rules={[{ required: true, message: 'Please select a workspace' }]}
        >
          <Select placeholder="Select workspace">
            {workspaces.map(workspace => (
              <Option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="category"
          label="Category"
          rules={[{ required: true, message: 'Please select a category' }]}
        >
          <Select placeholder="Select category">
            {DOCUMENT_CATEGORIES.map(category => (
              <Option key={category} value={category}>
                {category.charAt(0).toUpperCase() + category.slice(1)}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="Tags">
          <div>
            {tags.map(tag => (
              <Tag
                key={tag}
                closable
                onClose={() => handleTagClose(tag)}
              >
                {tag}
              </Tag>
            ))}
            {inputVisible ? (
              <Input
                type="text"
                size="small"
                style={{ width: 100 }}
                value={inputValue}
                onChange={handleTagInputChange}
                onBlur={handleTagInputConfirm}
                onPressEnter={handleTagInputConfirm}
                autoFocus
              />
            ) : (
              <Tag onClick={showTagInput} style={{ cursor: 'pointer' }}>
                <PlusOutlined /> Add tag
              </Tag>
            )}
          </div>
        </Form.Item>

        <Form.Item label="Keywords">
          <div>
            {keywords.map(keyword => (
              <Tag
                key={keyword}
                closable
                onClose={() => handleKeywordClose(keyword)}
                color="blue"
              >
                {keyword}
              </Tag>
            ))}
            {keywordInputVisible ? (
              <Input
                type="text"
                size="small"
                style={{ width: 100 }}
                value={keywordInputValue}
                onChange={handleKeywordInputChange}
                onBlur={handleKeywordInputConfirm}
                onPressEnter={handleKeywordInputConfirm}
                autoFocus
              />
            ) : (
              <Tag onClick={showKeywordInput} style={{ cursor: 'pointer' }}>
                <PlusOutlined /> Add keyword
              </Tag>
            )}
          </div>
        </Form.Item>

        <Form.Item label="Metadata">
          <div>
            {metadataEntries.map(entry => (
              <div key={entry.id} style={{ marginBottom: 8 }}>
                <Space>
                  <Input
                    placeholder="Key"
                    value={entry.key}
                    onChange={(e) => updateMetadataEntry(entry.id, 'key', e.target.value)}
                    style={{ width: 120 }}
                  />
                  <Input
                    placeholder="Value"
                    value={entry.value}
                    onChange={(e) => updateMetadataEntry(entry.id, 'value', e.target.value)}
                    style={{ width: 200 }}
                  />
                  <Button 
                    size="small" 
                    danger 
                    onClick={() => removeMetadataEntry(entry.id)}
                  >
                    Remove
                  </Button>
                </Space>
              </div>
            ))}
            <Button 
              type="dashed" 
              onClick={addMetadataEntry} 
              style={{ width: '100%' }}
            >
              <PlusOutlined /> Add metadata
            </Button>
          </div>
        </Form.Item>

        <Form.Item
          name="is_public"
          valuePropName="checked"
        >
          <Switch checkedChildren="Public" unCheckedChildren="Private" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default DocumentEdit;