import { useState } from 'react'
import {
  Layout,
  Form,
  Input,
  Button,
  Drawer,
  Statistic,
  Typography,
  Table,
  Tag,
  Space,
  Divider,
  message,
  Row,
  Col,
  Card,
} from 'antd'
import axios from 'axios'

const { Header, Content } = Layout
const { TextArea } = Input
const { Text } = Typography

export default function Simulate() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [result, setResult] = useState(null)

  const handleCompare = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)
      const resp = await axios.post('/api/composition_compare', {
        original_text: values.original_text,
        candidate_text: values.candidate_text,
      })
      setResult(resp.data)
      setDrawerOpen(true)
    } catch (err) {
      if (err?.response?.data?.detail?.msg) {
        message.error(err.response.data.detail.msg)
      } else if (err?.errorFields) {
        // 表单校验错误，antd 自动展示，无需额外处理
      } else {
        message.error('请求失败，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    form.resetFields()
    setResult(null)
    setDrawerOpen(false)
  }

  const detailColumns = [
    {
      title: '当前作文句子',
      dataIndex: 'sentence',
      key: 'sentence',
      width: 260,
      ellipsis: true,
    },
    {
      title: '目标作文句子',
      dataIndex: 'best_match',
      key: 'best_match',
      width: 260,
      ellipsis: true,
    },
    {
      title: '整句重复率',
      dataIndex: 'sentence_score',
      key: 'sentence_score',
      width: 100,
      render: (val) => `${(val * 100).toFixed(2)}%`,
    },
    {
      title: '是否重复句子',
      dataIndex: 'is_repeated',
      key: 'is_repeated',
      width: 110,
      render: (val) =>
        val ? <Tag color="red">是</Tag> : <Tag color="default">否</Tag>,
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header style={{ background: '#fff', borderBottom: '1px solid #e8e8e8', padding: '0 32px' }}>
        <Text strong style={{ fontSize: 18 }}>作文查重系统</Text>
      </Header>

      <Content style={{ padding: '24px 32px' }}>
        <Card bordered={false} style={{ borderRadius: 8 }}>
          <Form form={form} layout="vertical">
            <Row gutter={32}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="original_text"
                  label={<Text strong>当前作文</Text>}
                  rules={[{ required: true, message: '当前作文不能为空' }]}
                >
                  <TextArea
                    placeholder="请输入当前作文内容..."
                    style={{ height: 400, resize: 'none' }}
                    allowClear
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="candidate_text"
                  label={<Text strong>目标作文</Text>}
                  rules={[{ required: true, message: '目标作文不能为空' }]}
                >
                  <TextArea
                    placeholder="请输入目标作文内容..."
                    style={{ height: 400, resize: 'none' }}
                    allowClear
                  />
                </Form.Item>
              </Col>
            </Row>

            <Space>
              <Button type="primary" loading={loading} onClick={handleCompare}>
                查重
              </Button>
              <Button onClick={handleReset}>重置</Button>
            </Space>
          </Form>
        </Card>
      </Content>

      <Drawer
        title="查重结果"
        placement="right"
        width="65%"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose={false}
      >
        {result && (
          <>
            <Row gutter={32} style={{ marginBottom: 24 }}>
              <Col span={8}>
                <Statistic
                  title="文章重复率"
                  value={(result.symmetry_rate * 100).toFixed(2)}
                  suffix="%"
                  valueStyle={{
                    color: result.symmetry_rate >= 0.7 ? '#cf1322' : result.symmetry_rate >= 0.4 ? '#d46b08' : '#3f8600',
                  }}
                />
              </Col>
              <Col span={8}>
                <div>
                  <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>句子重复率</Text>
                  <Text strong style={{ fontSize: 20 }}>
                    {(result.sentence_repeat_rate * 100).toFixed(2)}%
                  </Text>
                </div>
              </Col>
              <Col span={8}>
                <div>
                  <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>词组重复率</Text>
                  <Text strong style={{ fontSize: 20 }}>
                    {(result.word_repeat_rate * 100).toFixed(2)}%
                  </Text>
                </div>
              </Col>
            </Row>

            <Divider orientation="left">句子比对详情</Divider>

            <Table
              dataSource={result.details}
              columns={detailColumns}
              rowKey={(_, idx) => idx}
              size="small"
              pagination={{ pageSize: 20, showSizeChanger: false }}
              scroll={{ x: 730 }}
            />
          </>
        )}
      </Drawer>
    </Layout>
  )
}
