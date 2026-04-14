/**
 * Agent node - represents a single agent execution step.
 */

import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { RobotOutlined } from '@ant-design/icons';
import type { CanvasNodeData } from '../types';
import styles from '../index.module.less';

function AgentNodeInner({ data, selected }: NodeProps<any>) {
  return (
    <div className={`${styles.canvasNode} ${selected ? styles.selected : ''}`}>
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{ background: '#1677ff', width: 10, height: 10 }}
      />
      <div className={`${styles.canvasNodeHeader} ${styles.agent}`}>
        <RobotOutlined />
        <span>{data.label || '智能体'}</span>
      </div>
      <div className={styles.canvasNodeBody}>
        {data.agent_id ? (
          <div className={styles.agentName}>{data.agent_id}</div>
        ) : (
          <div style={{ color: '#ff4d4f', fontSize: 11 }}>未选择智能体</div>
        )}
        {data.description && (
          <div style={{ marginTop: 4, opacity: 0.6, fontSize: 11 }}>
            {data.description}
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        style={{ background: '#1677ff', width: 10, height: 10 }}
      />
    </div>
  );
}

export const AgentNodeComponent = memo(AgentNodeInner);
