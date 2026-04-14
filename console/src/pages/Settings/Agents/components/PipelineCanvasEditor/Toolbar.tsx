/**
 * Canvas Toolbar - top bar with save, run, zoom controls.
 */

import { memo } from 'react';
import { Button, Space, Popconfirm } from 'antd';
import {
  SaveOutlined,
  PlayCircleOutlined,
  ExpandOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import styles from '../index.module.less';

interface ToolbarProps {
  onSave: () => void;
  onRun: () => void;
  onAutoLayout: () => void;
  onDeleteSelected: () => void;
  saving: boolean;
  hasSelection: boolean;
}

function ToolbarInner({ onSave, onRun, onAutoLayout, onDeleteSelected, saving, hasSelection }: ToolbarProps) {
  const { t } = useTranslation();

  return (
    <div className={styles.canvasToolbar}>
      <div className={styles.leftActions}>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={onSave}
          loading={saving}
        >
          {t('common.save', '保存')}
        </Button>
        <Button
          icon={<PlayCircleOutlined />}
          onClick={onRun}
        >
          {t('pipeline.run', '运行')}
        </Button>
      </div>
      <div className={styles.rightActions}>
        <Button
          icon={<ExpandOutlined />}
          onClick={onAutoLayout}
          title="自动布局"
        />
        <Popconfirm
          title="确认删除"
          description="确定要删除选中的节点/连线吗？"
          onConfirm={onDeleteSelected}
          disabled={!hasSelection}
        >
          <Button
            icon={<DeleteOutlined />}
            disabled={!hasSelection}
            danger
          />
        </Popconfirm>
      </div>
    </div>
  );
}

export const Toolbar = memo(ToolbarInner);
