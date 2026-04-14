/**
 * Sub-Pipeline node - references another pipeline.
 */

import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { ApartmentOutlined } from '@ant-design/icons';
import styles from '../index.module.less';

function SubPipelineNodeInner({ data, selected }: { data: any; selected?: boolean }) {
  return (
    <div className={`${styles.canvasNode} ${selected ? styles.selected : ''}`}>
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        style={{ background: '#eb2f96', width: 10, height: 10 }}
      />
      <div className={`${styles.canvasNodeHeader} ${styles.sub_pipeline}`}>
        <ApartmentOutlined />
        <span>{data.label || '子编排'}</span>
      </div>
      <div className={styles.canvasNodeBody}>
        {data.sub_pipeline_id ? (
          <div className={styles.agentName}>引用: {data.sub_pipeline_id}</div>
        ) : (
          <div style={{ color: '#ff4d4f', fontSize: 11 }}>未选择子编排</div>
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
        style={{ background: '#eb2f96', width: 10, height: 10 }}
      />
    </div>
  );
}

export const SubPipelineNodeComponent = memo(SubPipelineNodeInner);
