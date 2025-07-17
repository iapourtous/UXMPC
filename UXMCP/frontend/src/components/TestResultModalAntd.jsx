import React from 'react';
import { Modal, Descriptions, Tag, Card, Row, Col, Alert, Empty, Collapse, Typography } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Panel } = Collapse;
const { Text, Title } = Typography;

const TestResultModalAntd = ({ results, onClose }) => {
  if (!results) return null;

  const getStatusTag = (status) => {
    if (status >= 200 && status < 300) return <Tag color="success">Status {status}</Tag>;
    if (status >= 400 && status < 500) return <Tag color="warning">Status {status}</Tag>;
    if (status >= 500) return <Tag color="error">Status {status}</Tag>;
    return <Tag>Status {status}</Tag>;
  };

  const getValidationTag = (valid) => {
    return valid 
      ? <Tag icon={<CheckCircleOutlined />} color="success">PASS</Tag>
      : <Tag icon={<CloseCircleOutlined />} color="error">FAIL</Tag>;
  };

  return (
    <Modal
      title={`Test Results: ${results.service?.name || 'Unknown Service'}`}
      open={true}
      onCancel={onClose}
      width={1000}
      footer={null}
    >
      {/* Service Info */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions size="small" column={3}>
          <Descriptions.Item label="Service Type">
            <Tag>{results.service?.type || 'N/A'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Route">
            <Tag color="blue">{results.service?.route || 'N/A'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="LLM Profile">
            <Tag color="purple">{results.llm_profile || 'N/A'}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Summary Statistics */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Title level={3} style={{ color: '#1890ff', margin: 0 }}>
              {results.summary?.total || 0}
            </Title>
            <Text type="secondary">Total Tests</Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Title level={3} style={{ color: '#52c41a', margin: 0 }}>
              {results.summary?.passed || 0}
            </Title>
            <Text type="secondary">Passed</Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Title level={3} style={{ color: '#ff4d4f', margin: 0 }}>
              {results.summary?.failed || 0}
            </Title>
            <Text type="secondary">Failed</Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Title level={3} style={{ color: '#722ed1', margin: 0 }}>
              {results.summary?.success_rate || '0%'}
            </Title>
            <Text type="secondary">Success Rate</Text>
          </Card>
        </Col>
      </Row>

      {/* Test Results */}
      <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
        {results.results && results.results.length > 0 ? (
          <Collapse>
            {results.results.map((result, index) => (
              <Panel
                key={index}
                header={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>
                      <strong>{result.test_case?.name || 'Unnamed Test'}</strong>
                      {result.test_case?.description && (
                        <Text type="secondary" style={{ marginLeft: 8 }}>
                          - {result.test_case.description}
                        </Text>
                      )}
                    </span>
                    {getValidationTag(result.validation?.valid)}
                  </div>
                }
              >
                <Row gutter={16}>
                  <Col span={12}>
                    <Card 
                      size="small" 
                      title="Parameters" 
                      type="inner"
                      bodyStyle={{ backgroundColor: '#f5f5f5' }}
                    >
                      <pre style={{ margin: 0, fontSize: '12px' }}>
                        {JSON.stringify(result.test_case?.params || {}, null, 2)}
                      </pre>
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card 
                      size="small" 
                      title="Response" 
                      type="inner"
                      bodyStyle={{ backgroundColor: '#f5f5f5' }}
                    >
                      {getStatusTag(result.execution?.status || 0)}
                      {result.execution?.error ? (
                        <Alert
                          message="Error"
                          description={result.execution.error}
                          type="error"
                          showIcon
                          style={{ marginTop: 8 }}
                        />
                      ) : (
                        <pre style={{ margin: '8px 0 0 0', fontSize: '12px' }}>
                          {JSON.stringify(result.execution?.response || {}, null, 2)}
                        </pre>
                      )}
                    </Card>
                  </Col>
                </Row>

                {result.validation?.issues && result.validation.issues.length > 0 && (
                  <Alert
                    message="Validation Issues"
                    description={
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {result.validation.issues.map((issue, i) => (
                          <li key={i}>
                            {typeof issue === 'string' 
                              ? issue 
                              : typeof issue === 'object' && issue !== null
                                ? (() => {
                                    if (issue.issue && (issue.expected || issue.actual)) {
                                      return (
                                        <div>
                                          <Text>{issue.issue}</Text>
                                          {issue.expected && (
                                            <div style={{ marginLeft: 16 }}>
                                              <Text strong>Expected:</Text> <Text code>{JSON.stringify(issue.expected)}</Text>
                                            </div>
                                          )}
                                          {issue.actual && (
                                            <div style={{ marginLeft: 16 }}>
                                              <Text strong>Actual:</Text> <Text code>{JSON.stringify(issue.actual)}</Text>
                                            </div>
                                          )}
                                        </div>
                                      );
                                    }
                                    return issue.issue || issue.message || JSON.stringify(issue);
                                  })()
                                : String(issue)
                            }
                          </li>
                        ))}
                      </ul>
                    }
                    type="error"
                    showIcon
                    style={{ marginTop: 16 }}
                  />
                )}

                {result.validation?.summary && (
                  <Alert
                    message="Validation Summary"
                    description={result.validation.summary}
                    type="info"
                    icon={<InfoCircleOutlined />}
                    style={{ marginTop: 16 }}
                  />
                )}
              </Panel>
            ))}
          </Collapse>
        ) : (
          <Empty description="No test results available" />
        )}
      </div>
    </Modal>
  );
};

export default TestResultModalAntd;