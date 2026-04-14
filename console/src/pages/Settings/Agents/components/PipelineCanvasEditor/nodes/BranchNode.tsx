/**
 * Branch node - conditional routing with multiple labeled outputs.
 */

import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { SplitCellsOutlined } from '@ant-design/icons';
import styles from '../index.module.less';

function BranchNodeInner({ data, selected }: { data: any; selected?: boolean }) {
  const conditions = data.condition ? [data.condition] : ['条件1', '条件2'];

  return (
    <div className={`${styles.canvasNode} ${selected ? styles.selected : ''}`} style={{ minWidth: 200 }}>
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{ background: '#fa8c16', width: 10, height: 10 }}
      />
      <div className={`${styles.canvasNodeHeader} ${styles.branch}`}>
        <SplitCellsOutlined />
        <span>{data.label || '分支'}</span>
      </div>
      <div className={styles.canvasNodeBody}>
        {conditions.map((cond: string, i: number) => (
          <div
            key={i}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 11,
            }}
          >
            <span>{cond}</span>
            <Handle
              type="source"
              position={Position.Bottom}
              id={`out-${i}`}
              style={{
                position: 'relative',
                top: 0,
                background: '#fa8c16',
                width: 8,
                height: 8,
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export const BranchNodeComponent = memo(BranchNodeInner);
