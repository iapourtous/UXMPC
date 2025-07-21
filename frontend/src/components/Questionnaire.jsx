import React, { useState } from 'react';
import { Modal, Form, Input, Select, Radio, Checkbox, InputNumber, Button, Space, Typography } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

const { Option } = Select;
const { Text } = Typography;

const Questionnaire = ({ visible, questionnaire, onSubmit, onCancel, loading }) => {
  const [form] = Form.useForm();
  const [answers, setAnswers] = useState({});

  const renderQuestion = (question) => {
    const commonProps = {
      placeholder: question.context || `Enter ${question.question.toLowerCase()}`,
    };

    switch (question.type) {
      case 'choice':
        return (
          <Radio.Group {...commonProps}>
            {question.options?.map(option => (
              <Radio key={option} value={option}>{option}</Radio>
            ))}
          </Radio.Group>
        );

      case 'multiselect':
        return (
          <Checkbox.Group options={question.options} {...commonProps} />
        );

      case 'boolean':
        return (
          <Radio.Group {...commonProps}>
            <Radio value={true}>Yes</Radio>
            <Radio value={false}>No</Radio>
          </Radio.Group>
        );

      case 'number':
        return (
          <InputNumber style={{ width: '100%' }} {...commonProps} />
        );

      case 'text':
      default:
        return (
          <Input {...commonProps} />
        );
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // Transform form values to match question IDs
      const formattedAnswers = {};
      questionnaire?.questions?.forEach(question => {
        const value = values[question.id];
        formattedAnswers[question.id] = value !== undefined ? value : question.default;
      });

      onSubmit(formattedAnswers);
    } catch (error) {
      console.error('Form validation failed:', error);
    }
  };

  const getInitialValues = () => {
    const initialValues = {};
    questionnaire?.questions?.forEach(question => {
      if (question.default !== undefined) {
        initialValues[question.id] = question.default;
      }
    });
    return initialValues;
  };

  if (!questionnaire) return null;

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <QuestionCircleOutlined />
          <span>Help us understand your needs better</span>
        </div>
      }
      visible={visible}
      onCancel={onCancel}
      footer={[
        <Button key="skip" onClick={() => onSubmit({})}>
          Skip Questions
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
          Generate Response
        </Button>
      ]}
      width={600}
      destroyOnClose
    >
      <div style={{ marginBottom: '16px' }}>
        <Text type="secondary">
          Query type: <Text strong>{questionnaire.query_type}</Text>
        </Text>
      </div>

      <Form
        form={form}
        layout="vertical"
        initialValues={getInitialValues()}
      >
        {questionnaire.questions?.map((question, index) => (
          <Form.Item
            key={question.id}
            name={question.id}
            label={
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>{question.question}</span>
                {question.required && <span style={{ color: 'red' }}>*</span>}
              </div>
            }
            rules={question.required ? [{ required: true, message: 'This field is required' }] : []}
            extra={question.context}
          >
            {renderQuestion(question)}
          </Form.Item>
        ))}
      </Form>

      <div style={{ marginTop: '16px', padding: '12px', background: '#f6f6f6', borderRadius: '6px' }}>
        <Text type="secondary" style={{ fontSize: '12px' }}>
          💡 These questions help us create a more personalized and relevant response for you.
          You can skip them if you prefer to use default settings.
        </Text>
      </div>
    </Modal>
  );
};

export default Questionnaire;