import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Button,
  Space,
  Alert,
  Divider,
  Typography,
  Spin,
  message,
  Row,
  Col,
  Tag,
  Collapse,
  Descriptions,
  Badge,
  Tabs,
  Empty,
  Switch
} from 'antd';
import {
  PlayCircleOutlined,
  ArrowLeftOutlined,
  RobotOutlined,
  ApiOutlined,
  ToolOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  BugOutlined,
  DatabaseOutlined,
  BulbOutlined,
  HistoryOutlined,
  UserOutlined,
  BookOutlined,
  SmileOutlined,
  SettingOutlined
} from '@ant-design/icons';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { javascript } from '@codemirror/lang-javascript';
import { agentsApi } from '../services/api';
import ServiceLogs from './ServiceLogs';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;
const { TabPane } = Tabs;

const AgentTest = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [conversationHistory, setConversationHistory] = useState([]);
  const [useConversationHistory, setUseConversationHistory] = useState(true);

  useEffect(() => {
    fetchAgent();
  }, [id]);

  const fetchAgent = async () => {
    setLoading(true);
    try {
      const response = await agentsApi.get(id);
      setAgent(response.data);
      
      // Set default input based on schema
      if (response.data.input_schema === 'text') {
        setInputValue('Hello, can you help me?');
      } else {
        setInputValue(JSON.stringify({
          query: "What can you help me with?",
          context: {}
        }, null, 2));
      }
    } catch (error) {
      message.error('Failed to fetch agent');
      navigate('/agents');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    setExecuting(true);
    setExecutionResult(null);
    
    try {
      let input;
      if (agent.input_schema === 'text') {
        input = inputValue;
      } else {
        try {
          input = JSON.parse(inputValue);
        } catch {
          message.error('Invalid JSON input');
          setExecuting(false);
          return;
        }
      }

      // Build conversation history if memory is enabled and option is checked
      let history = null;
      if (agent.memory_enabled && useConversationHistory && conversationHistory.length > 0) {
        history = conversationHistory;
      }

      const response = await agentsApi.execute(id, {
        input,
        conversation_history: history,
        execution_options: {}
      });
      
      setExecutionResult(response.data);
      
      if (response.data.success) {
        message.success('Agent executed successfully');
        
        // Add to conversation history if memory is enabled
        if (agent.memory_enabled) {
          const newHistory = [...conversationHistory];
          newHistory.push({
            role: 'user',
            content: typeof input === 'string' ? input : JSON.stringify(input)
          });
          newHistory.push({
            role: 'assistant',
            content: typeof response.data.output === 'string' 
              ? response.data.output 
              : JSON.stringify(response.data.output)
          });
          setConversationHistory(newHistory);
        }
      } else {
        message.error('Agent execution failed');
      }
    } catch (error) {
      message.error('Failed to execute agent');
      setExecutionResult({
        success: false,
        error: error.response?.data?.detail || 'Unknown error occurred'
      });
    } finally {
      setExecuting(false);
    }
  };

  const clearConversation = () => {
    setConversationHistory([]);
    message.success('Conversation history cleared');
  };

  if (loading || !agent) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  const renderOutput = () => {
    if (!executionResult) return null;

    if (!executionResult.success) {
      return (
        <Alert
          message="Execution Failed"
          description={executionResult.error}
          type="error"
          showIcon
          icon={<CloseCircleOutlined />}
        />
      );
    }

    const output = executionResult.output;
    
    if (agent.output_schema === 'text') {
      return (
        <Card size="small">
          <Paragraph>{output}</Paragraph>
        </Card>
      );
    } else {
      return (
        <CodeMirror
          value={JSON.stringify(output, null, 2)}
          height="300px"
          extensions={[json()]}
          editable={false}
        />
      );
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <RobotOutlined style={{ fontSize: '24px' }} />
            <span>Test Agent: {agent.name}</span>
            {agent.active ? (
              <Tag color="green" icon={<CheckCircleOutlined />}>Active</Tag>
            ) : (
              <Tag color="default">Inactive</Tag>
            )}
          </Space>
        }
        extra={
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/agents')}
          >
            Back to Agents
          </Button>
        }
      >
        <Tabs defaultActiveKey="overview">
          <TabPane tab="Overview" key="overview">
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="Endpoint">
                <Tag icon={<ApiOutlined />} color="blue">{agent.endpoint}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="LLM Profile">
                <Tag color="purple">{agent.llm_profile}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Input Schema">
                {agent.input_schema === 'text' ? 'Plain Text' : 'JSON'}
              </Descriptions.Item>
              <Descriptions.Item label="Output Schema">
                {agent.output_schema === 'text' ? 'Plain Text' : 'JSON'}
              </Descriptions.Item>
              <Descriptions.Item label="Features">
                <Space>
                  {agent.memory_enabled && (
                    <Tag icon={<DatabaseOutlined />} color="blue">Memory</Tag>
                  )}
                  {agent.reasoning_strategy !== 'standard' && (
                    <Tag icon={<BulbOutlined />} color="purple">{agent.reasoning_strategy}</Tag>
                  )}
                  {agent.backstory && (
                    <Tag icon={<BookOutlined />} color="gold">Identity</Tag>
                  )}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="MCP Services">
                {agent.mcp_services.length > 0 ? (
                  <Space wrap>
                    {agent.mcp_services.map(service => (
                      <Tag key={service} icon={<ToolOutlined />}>{service}</Tag>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">No services</Text>
                )}
              </Descriptions.Item>
              {agent.description && (
                <Descriptions.Item label="Description" span={2}>
                  {agent.description}
                </Descriptions.Item>
              )}
            </Descriptions>
          </TabPane>
          
          {(agent.backstory || agent.objectives?.length > 0 || agent.constraints?.length > 0) && (
            <TabPane tab={<span><BookOutlined /> Identity</span>} key="identity">
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                {agent.backstory && (
                  <div>
                    <Title level={5}>Backstory</Title>
                    <Card size="small">
                      <Paragraph>{agent.backstory}</Paragraph>
                    </Card>
                  </div>
                )}
                
                {agent.objectives?.length > 0 && (
                  <div>
                    <Title level={5}>Objectives</Title>
                    <Card size="small">
                      {agent.objectives.map((obj, index) => (
                        <div key={index}>
                          <BulbOutlined /> {obj}
                        </div>
                      ))}
                    </Card>
                  </div>
                )}
                
                {agent.constraints?.length > 0 && (
                  <div>
                    <Title level={5}>Constraints</Title>
                    <Card size="small">
                      {agent.constraints.map((constraint, index) => (
                        <div key={index}>
                          <CloseCircleOutlined /> {constraint}
                        </div>
                      ))}
                    </Card>
                  </div>
                )}
              </Space>
            </TabPane>
          )}
          
          {agent.personality_traits && (
            <TabPane tab={<span><SmileOutlined /> Personality</span>} key="personality">
              <Descriptions bordered size="small">
                <Descriptions.Item label="Tone">
                  <Tag>{agent.personality_traits.tone}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Verbosity">
                  <Tag>{agent.personality_traits.verbosity}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Empathy">
                  <Tag>{agent.personality_traits.empathy}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Humor">
                  <Tag>{agent.personality_traits.humor}</Tag>
                </Descriptions.Item>
              </Descriptions>
            </TabPane>
          )}
          
          {agent.decision_policies && (
            <TabPane tab={<span><SettingOutlined /> Policies</span>} key="policies">
              <Descriptions bordered size="small">
                <Descriptions.Item label="Confidence Threshold">
                  {agent.decision_policies.confidence_threshold}
                </Descriptions.Item>
                <Descriptions.Item label="Max Retries">
                  {agent.decision_policies.max_retries}
                </Descriptions.Item>
                <Descriptions.Item label="Auto-correct Errors">
                  {agent.decision_policies.auto_correct_errors ? 'Yes' : 'No'}
                </Descriptions.Item>
                <Descriptions.Item label="Explain Decisions">
                  {agent.decision_policies.explain_decisions ? 'Yes' : 'No'}
                </Descriptions.Item>
                {agent.decision_policies.require_confirmation?.length > 0 && (
                  <Descriptions.Item label="Require Confirmation" span={2}>
                    <Space>
                      {agent.decision_policies.require_confirmation.map(action => (
                        <Tag key={action}>{action}</Tag>
                      ))}
                    </Space>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </TabPane>
          )}
        </Tabs>

        <Divider />

        {!agent.active && (
          <Alert
            message="Agent is not active"
            description="This agent must be activated before it can be executed via its endpoint."
            type="warning"
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}

        <Row gutter={24}>
          <Col span={12}>
            <Card 
              title="Input" 
              size="small"
              extra={
                agent.memory_enabled && (
                  <Space>
                    <span>Use conversation history:</span>
                    <Switch
                      checked={useConversationHistory}
                      onChange={setUseConversationHistory}
                      checkedChildren="Yes"
                      unCheckedChildren="No"
                    />
                    {conversationHistory.length > 0 && (
                      <Button
                        size="small"
                        icon={<DatabaseOutlined />}
                        onClick={() => navigate(`/agents/${id}/memory`)}
                      >
                        Memory
                      </Button>
                    )}
                  </Space>
                )
              }
            >
              <Form.Item
                label={`Input (${agent.input_schema === 'text' ? 'Plain Text' : 'JSON'})`}
                extra={agent.input_schema !== 'text' && "Enter valid JSON"}
              >
                <CodeMirror
                  value={inputValue}
                  height="200px"
                  extensions={agent.input_schema === 'text' ? [javascript()] : [json()]}
                  onChange={(value) => setInputValue(value)}
                />
              </Form.Item>
              <Space style={{ width: '100%' }} direction="vertical">
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleExecute}
                  loading={executing}
                  block
                >
                  Execute Agent
                </Button>
                {agent.memory_enabled && conversationHistory.length > 0 && (
                  <Button
                    icon={<HistoryOutlined />}
                    onClick={clearConversation}
                    block
                  >
                    Clear Conversation ({conversationHistory.length / 2} exchanges)
                  </Button>
                )}
              </Space>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="Output" size="small">
              {executing ? (
                <div style={{ textAlign: 'center', padding: '50px' }}>
                  <Spin tip="Executing agent..." />
                </div>
              ) : executionResult ? (
                renderOutput()
              ) : (
                <Empty description="No execution results yet" />
              )}
            </Card>
          </Col>
        </Row>

        {executionResult && executionResult.success && (
          <Tabs defaultActiveKey="details" style={{ marginTop: 24 }}>
            <TabPane tab="Execution Details" key="details">
              <Descriptions bordered size="small">
                <Descriptions.Item label="Execution ID" span={3}>
                  <Text code>{executionResult.execution_id}</Text>
                </Descriptions.Item>
                {executionResult.iterations && (
                  <Descriptions.Item label="Iterations">
                    <Badge count={executionResult.iterations} style={{ backgroundColor: '#52c41a' }} />
                  </Descriptions.Item>
                )}
                {executionResult.usage && (
                  <>
                    <Descriptions.Item label="Prompt Tokens">
                      {executionResult.usage.prompt_tokens}
                    </Descriptions.Item>
                    <Descriptions.Item label="Completion Tokens">
                      {executionResult.usage.completion_tokens}
                    </Descriptions.Item>
                    <Descriptions.Item label="Total Tokens">
                      {executionResult.usage.total_tokens}
                    </Descriptions.Item>
                  </>
                )}
              </Descriptions>
            </TabPane>
            
            {executionResult.tool_calls && executionResult.tool_calls.length > 0 && (
              <TabPane tab={`Tool Calls (${executionResult.tool_calls.length})`} key="tools">
                <Collapse>
                  {executionResult.tool_calls.map((call, index) => (
                    <Panel
                      header={
                        <Space>
                          <ToolOutlined />
                          <Text strong>{call.tool}</Text>
                          <Text type="secondary">Call #{index + 1}</Text>
                        </Space>
                      }
                      key={index}
                    >
                      <Row gutter={16}>
                        <Col span={12}>
                          <Title level={5}>Arguments</Title>
                          <CodeMirror
                            value={JSON.stringify(JSON.parse(call.arguments), null, 2)}
                            height="150px"
                            extensions={[json()]}
                            editable={false}
                          />
                        </Col>
                        <Col span={12}>
                          <Title level={5}>Result</Title>
                          <CodeMirror
                            value={JSON.stringify(call.result, null, 2)}
                            height="150px"
                            extensions={[json()]}
                            editable={false}
                          />
                        </Col>
                      </Row>
                    </Panel>
                  ))}
                </Collapse>
              </TabPane>
            )}
            
            {agent.memory_enabled && conversationHistory.length > 0 && (
              <TabPane tab={<span><HistoryOutlined /> Conversation History</span>} key="history">
                <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  {conversationHistory.map((msg, index) => (
                    <Card
                      key={index}
                      size="small"
                      style={{ 
                        marginBottom: 8,
                        backgroundColor: msg.role === 'user' ? '#f0f5ff' : '#f6ffed'
                      }}
                      title={
                        <Space>
                          {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                          <span>{msg.role === 'user' ? 'User' : 'Assistant'}</span>
                        </Space>
                      }
                    >
                      <Paragraph style={{ margin: 0 }}>{msg.content}</Paragraph>
                    </Card>
                  ))}
                </div>
              </TabPane>
            )}
            
            {executionResult.execution_id && (
              <TabPane tab={<span><BugOutlined /> Logs</span>} key="logs">
                <ServiceLogs
                  serviceId={`agent_${id}`}
                  executionId={executionResult.execution_id}
                  embedded
                />
              </TabPane>
            )}
          </Tabs>
        )}
      </Card>
    </div>
  );
};

export default AgentTest;