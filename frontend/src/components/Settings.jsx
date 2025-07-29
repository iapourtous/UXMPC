import React, { useState, useEffect } from 'react';
import { Card, Form, Select, Input, InputNumber, Switch, Button, message, Spin, Alert, Divider, Typography, Space, Tooltip } from 'antd';
import { SaveOutlined, ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Settings = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [settings, setSettings] = useState(null);

  // Fetch available LLM profiles
  const fetchLlmProfiles = async () => {
    try {
      const response = await axios.get(`${API_URL}/settings/llm-profiles-text`);
      setLlmProfiles(response.data);
    } catch (error) {
      console.error('Failed to fetch LLM profiles:', error);
      message.error('Failed to load LLM profiles');
    }
  };

  // Fetch current settings
  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/settings`);
      setSettings(response.data);
      
      // Set form values
      form.setFieldsValue({
        summary_llm_profile: response.data.summary_llm_profile || undefined,
        user_context: response.data.user_context || '',
        compaction_enabled: response.data.compaction_settings?.enabled ?? true,
        message_threshold: response.data.compaction_settings?.message_threshold ?? 5,
        preserve_last_n: response.data.compaction_settings?.preserve_last_n ?? 3,
        summary_max_tokens: response.data.compaction_settings?.summary_max_tokens ?? 100,
      });
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      message.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  // Save settings
  const handleSave = async (values) => {
    try {
      setSaving(true);
      
      const payload = {
        summary_llm_profile: values.summary_llm_profile || null,
        user_context: values.user_context?.trim() || null,
        compaction_settings: {
          enabled: values.compaction_enabled,
          message_threshold: values.message_threshold,
          preserve_last_n: values.preserve_last_n,
          summary_max_tokens: values.summary_max_tokens,
        }
      };

      await axios.put(`${API_URL}/settings`, payload);
      message.success('Settings saved successfully');
      
      // Refresh settings
      await fetchSettings();
    } catch (error) {
      console.error('Failed to save settings:', error);
      message.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  // Reset to defaults
  const handleReset = async () => {
    try {
      setLoading(true);
      await axios.post(`${API_URL}/settings/reset`);
      message.success('Settings reset to defaults');
      await fetchSettings();
    } catch (error) {
      console.error('Failed to reset settings:', error);
      message.error('Failed to reset settings');
    }
  };

  useEffect(() => {
    fetchLlmProfiles();
    fetchSettings();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>Global Settings</Title>
      <Paragraph>
        Configure system-wide settings for conversation management and user context.
      </Paragraph>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        autoComplete="off"
      >
        {/* User Context Section */}
        <Card title="User Context" style={{ marginBottom: 24 }}>
          <Alert
            message="User context is persistent information provided to all agents"
            description="This can include your preferences, language, expertise level, or any other relevant information that helps agents provide better responses."
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          
          <Form.Item
            name="user_context"
            label="User Context"
            tooltip="This context will be provided to all agents at the beginning of every conversation"
          >
            <TextArea
              rows={4}
              placeholder="Example: I am a Python developer with 5 years of experience. I prefer concise, technical explanations. I speak French and English."
              maxLength={1000}
              showCount
            />
          </Form.Item>
        </Card>

        {/* Conversation Compaction Section */}
        <Card title="Conversation Compaction" style={{ marginBottom: 24 }}>
          <Alert
            message="Automatic conversation compaction helps reduce token usage"
            description="When conversations become long, older messages are automatically summarized to keep the context manageable while preserving recent messages. The full conversation remains visible to you."
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Form.Item
            name="compaction_enabled"
            label="Enable Conversation Compaction"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.compaction_enabled !== currentValues.compaction_enabled}
          >
            {({ getFieldValue }) =>
              getFieldValue('compaction_enabled') && (
                <>
                  <Divider />
                  
                  <Form.Item
                    name="summary_llm_profile"
                    label="Summary LLM Profile"
                    tooltip="Select a text-only LLM profile to use for summarizing conversations"
                    rules={[{ required: true, message: 'Please select an LLM profile for summarization' }]}
                  >
                    <Select
                      placeholder="Select an LLM profile..."
                      allowClear
                      showSearch
                    >
                      {llmProfiles.map(profile => (
                        <Option key={profile} value={profile}>
                          {profile}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Space size="large" style={{ display: 'flex', marginBottom: 16 }}>
                    <Form.Item
                      name="message_threshold"
                      label={
                        <Space>
                          Message Threshold
                          <Tooltip title="Start compacting after this many messages">
                            <InfoCircleOutlined />
                          </Tooltip>
                        </Space>
                      }
                      rules={[{ required: true }]}
                    >
                      <InputNumber
                        min={2}
                        max={20}
                        style={{ width: 150 }}
                        addonAfter="messages"
                      />
                    </Form.Item>

                    <Form.Item
                      name="preserve_last_n"
                      label={
                        <Space>
                          Preserve Recent Messages
                          <Tooltip title="Number of recent messages to keep uncompacted">
                            <InfoCircleOutlined />
                          </Tooltip>
                        </Space>
                      }
                      rules={[{ required: true }]}
                    >
                      <InputNumber
                        min={1}
                        max={10}
                        style={{ width: 150 }}
                        addonAfter="messages"
                      />
                    </Form.Item>

                    <Form.Item
                      name="summary_max_tokens"
                      label={
                        <Space>
                          Summary Max Tokens
                          <Tooltip title="Maximum tokens allocated for the summary of old messages">
                            <InfoCircleOutlined />
                          </Tooltip>
                        </Space>
                      }
                      rules={[{ required: true }]}
                    >
                      <InputNumber
                        min={50}
                        max={500}
                        step={50}
                        style={{ width: 150 }}
                        addonAfter="tokens"
                      />
                    </Form.Item>
                  </Space>

                  <Alert
                    message="Example"
                    description={`With current settings: After ${form.getFieldValue('message_threshold') || 5} messages, the system will summarize older messages (except the last ${form.getFieldValue('preserve_last_n') || 3}) into ~${form.getFieldValue('summary_max_tokens') || 100} tokens.`}
                    type="success"
                    showIcon
                  />
                </>
              )
            }
          </Form.Item>
        </Card>

        {/* Action Buttons */}
        <Form.Item>
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              loading={saving}
              icon={<SaveOutlined />}
              size="large"
            >
              Save Settings
            </Button>
            <Button
              onClick={handleReset}
              icon={<ReloadOutlined />}
              size="large"
            >
              Reset to Defaults
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
};

export default Settings;