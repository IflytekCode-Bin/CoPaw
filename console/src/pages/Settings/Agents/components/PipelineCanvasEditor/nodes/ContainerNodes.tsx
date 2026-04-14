/**
 * Loop container node - wraps a sub-graph for iterative execution.
 * Parallel container node - forks execution into parallel branches.
 */

import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { SyncOutlined, BranchesOutlined } from '@ant-design/icons';
import styles from '../index.module.less';

function LoopNodeInner({ data, selected }: { data: any; selected?: boolean }) {
  return (
    <div className={`${styles.canvasNode} ${styles.containerNode} ${selected ? styles.selected : ''}`}>
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{ background: '#13c2c2', width: 10, height: 10 }}
      />
      <div className={styles.containerHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SyncOutlined style={{ color: '#13c2c2' }} />
          <span style={{ fontWeight: 500, fontSize: 13 }}>{data.label || '循环'}</span>
        </div>
        {data.max_iterations && (
          <span style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)' }}>
            最多 {data.max_iterations} 次
          </span>
        )}
      </div>
      <div className={styles.containerInner}>
        <div style={{ padding: 12, color: 'rgba(0,0,0,0.35)', fontSize: 12 }}>
          拖拽节点到此处
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        style={{ background: '#13c2c2', width: 10, height: 10 }}
      />
    </div>
  );
}

function ParallelNodeInner({ data, selected }: { data: any; selected?: boolean }) {
  return (
    <div className={`${styles.canvasNode} ${styles.containerNode} ${selected ? styles.selected : ''}`}>
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{ background: '#722ed1', width: 10, height: 10 }}
      />
      <div className={styles.containerHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BranchesOutlined style={{ color: '#722ed1' }} />
          <span style={{ fontWeight: 500, fontSize: 13 }}>{data.label || '并行'}</span>
        </div>
      </div>
      <div className={styles.containerInner}>
        <div style={{ padding: 12, color: 'rgba(0,0,0,0.35)', fontSize: 12 }}>
          拖拽节点到此处
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        style={{ background: '#722ed1', width: 10, height: 10 }}
      />
    </div>
  );
}

export const LoopNodeComponent = memo(LoopNodeInner);
export const ParallelNodeComponent = memo(ParallelNodeInner);
