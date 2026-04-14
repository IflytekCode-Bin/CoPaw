/**
 * Node Palette - left sidebar with draggable node types.
 */

import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  PlayCircleOutlined,
  StopOutlined,
  RobotOutlined,
  SplitCellsOutlined,
  SyncOutlined,
  BranchesOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import type { CanvasNodeType } from '../types';
import styles from './index.module.less';

interface NodePaletteProps {
  onDragStart: (event: React.DragEvent, nodeType: CanvasNodeType) => void;
}

const NODE_TYPES: Array<{
  type: CanvasNodeType;
  label: string;
  icon: React.ReactNode;
}> = [
  { type: 'start', label: '开始', icon: <PlayCircleOutlined /> },
  { type: 'end', label: '结束', icon: <StopOutlined /> },
  { type: 'agent', label: '智能体', icon: <RobotOutlined /> },
  { type: 'branch', label: '分支', icon: <SplitCellsOutlined /> },
  { type: 'parallel', label: '并行', icon: <BranchesOutlined /> },
  { type: 'loop', label: '循环', icon: <SyncOutlined /> },
  { type: 'sub_pipeline', label: '子编排', icon: <ApartmentOutlined /> },
];

function NodePaletteInner({ onDragStart }: NodePaletteProps) {
  const { t } = useTranslation();

  return (
    <div className={styles.nodePalette}>
      <h4>{t('pipeline.palette', '节点面板')}</h4>
      {NODE_TYPES.map((item) => (
        <div
          key={item.type}
          className={styles.paletteItem}
          draggable
          onDragStart={(event) => onDragStart(event, item.type)}
        >
          <span className={styles.icon}>{item.icon}</span>
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export const NodePalette = memo(NodePaletteInner);
