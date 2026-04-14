/**
 * Start and End nodes for the pipeline canvas.
 */

import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import type { CanvasNodeData } from '../types';
import styles from '../index.module.less';

function StartNodeInner({ data, selected }: NodeProps<any>) {
  return (
    <div className={`${styles.canvasNode} ${selected ? styles.selected : ''}`}>
      <div className={`${styles.canvasNodeHeader} ${styles.start}`}>
        <PlayCircleOutlined />
        <span>{data.label || '开始'}</span>
      </div>
      <div className={styles.canvasNodeBody}>
        <div style={{ opacity: 0.6, fontSize: 11 }}>Pipeline 入口</div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        style={{ background: '#52c41a', width: 10, height: 10 }}
      />
    </div>
  );
}

function EndNodeInner({ data, selected }: NodeProps<any>) {
  return (
    <div className={`${styles.canvasNode} ${selected ? styles.selected : ''}`}>
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{ background: '#ff4d4f', width: 10, height: 10 }}
      />
      <div className={`${styles.canvasNodeHeader} ${styles.end}`}>
        <StopOutlined />
        <span>{data.label || '结束'}</span>
      </div>
      <div className={styles.canvasNodeBody}>
        <div style={{ opacity: 0.6, fontSize: 11 }}>Pipeline 出口</div>
      </div>
    </div>
  );
}

export const StartNodeComponent = memo(StartNodeInner);
export const EndNodeComponent = memo(EndNodeInner);
