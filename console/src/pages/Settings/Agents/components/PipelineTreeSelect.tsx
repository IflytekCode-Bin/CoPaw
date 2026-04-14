import React, { useEffect, useState } from "react";
import { Select, Spin, Tag } from "antd";
import { pipelineApi } from "../../../../api/modules/pipeline";
import { useTranslation } from "react-i18next";

export interface PipelineTreeSelectProps {
  value?: string[];
  onChange?: (values: string[]) => void;
  excludeId?: string;
  disabled?: boolean;
}

export default function PipelineTreeSelect({
  value = [],
  onChange,
  excludeId,
  disabled,
}: PipelineTreeSelectProps) {
  const { t } = useTranslation();
  const [options, setOptions] = useState<Array<{
    value: string;
    label: string;
    owner_agent_id?: string;
    sub_pipeline_count: number;
  }>>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    pipelineApi
      .getSelectOptions(excludeId)
      .then((data) => {
        if (!cancelled) setOptions(data);
      })
      .catch(() => {
        // silently fail
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [excludeId]);

  return (
    <Select
      mode="multiple"
      allowClear
      placeholder={t("agent.pipeline.selectSubPipelines", "选择子编排")}
      value={value}
      onChange={onChange}
      disabled={disabled}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : null}
      optionRender={(option) => (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>{option.label}</span>
          {option.data.owner_agent_id && (
            <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
              {option.data.owner_agent_id}
            </Tag>
          )}
          {option.data.sub_pipeline_count > 0 && (
            <Tag style={{ fontSize: 11, margin: 0 }}>
              {option.data.sub_pipeline_count} {t("agent.pipeline.nested", "嵌套")}
            </Tag>
          )}
        </div>
      )}
    >
      {options.map((opt) => (
        <Select.Option key={opt.value} value={opt.value} data={opt}>
          {opt.label}
        </Select.Option>
      ))}
    </Select>
  );
}
