/**
 * Config Panel - right sidebar for configuring selected node.
 */

import { memo, useEffect } from 'react';
import { Form, Input, Select, InputNumber, Button, Space } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { PipelineCanvasNode } from '../types';
import styles from '../index.module.less';

interface ConfigPanelProps {
  node: PipelineCanvasNode | null;
  allAgents: Array<{ id: string; name: string }>;
  allPipelines: Array<{ id: string; name: string }>;
  onUpdate: (nodeId: string, data: Record<string, any>) => void;
  onClose: () => void;
}

function ConfigPanelInner({ node, allAgents, allPipelines, onUpdate, onClose }: ConfigPanelProps) {
  const { t } = useTranslation();
  const [form] = Form.useForm();

  useEffect(() => {
    if (node) {
      form.setFieldsValue({
        label: node.data.label,
        agent_id: node.data.agent_id,
        description: node.data.description,
        max_iterations: node.data.max_iterations,
        sub_pipeline_id: node.data.sub_pipeline_id,
        condition: node.data.condition,
      });
    }
  }, [node, form]);

  const handleFinish = (values: Record<string, any>) => {
    if (node) {
      onUpdate(node.id, values);
    }
  };

  if (!node) {
    return null;
  }

  const agentOptions = allAgents.map((a) => ({ value: a.id, label: a.name }));
  const pipelineOptions = allPipelines.map((p) => ({ value: p.id, label: p.name }));

  return (
    <div className={styles.configPanel}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h4 style={{ margin: 0 }}>{t('pipeline.nodeConfig', '节点配置')}</h4>
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} />
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        size="small"
      >
        <Form.Item label="节点名称" name="label" rules={[{ required: true, message: '请输入名称' }]}>
          <Input placeholder="输入节点名称" />
        </Form.Item>

        {node.type === 'agent' && (
          <Form.Item
            label="绑定智能体"
            name="agent_id"
            rules={[{ required: true, message: '请选择智能体' }]}
          >
            <Select
              placeholder="选择智能体"
              options={agentOptions}
              allowClear
            />
          </Form.Item>
        )}

        {node.type === 'sub_pipeline' && (
          <Form.Item
            label="引用子编排"
            name="sub_pipeline_id"
            rules={[{ required: true, message: '请选择子编排' }]}
          >
            <Select
              placeholder="选择子编排"
              options={pipelineOptions}
              allowClear
            />
          </Form.Item>
        )}

        {node.type === 'loop' && (
          <Form.Item
            label="最大循环次数"
            name="max_iterations"
            rules={[{ required: true, message: '请输入循环次数' }]}
          >
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
        )}

        {node.type === 'branch' && (
          <Form.Item label="条件描述" name="condition">
            <Input placeholder="如: 测试通过" />
          </Form.Item>
        )}

        <Form.Item label="描述" name="description">
          <Input.TextArea rows={3} placeholder="可选描述" />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" block>
            {t('common.save', '保存')}
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}

export const ConfigPanel = memo(ConfigPanelInner);
