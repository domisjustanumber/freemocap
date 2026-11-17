import IconButton from "@/components/ui-components/IconButton";
import { openPipelineMetricsWindow } from "@/services/electron-ipc/open-pipeline-metrics-window";
import { PipelineType, type PipelineGroup } from "@/store/slices/pipelines";

/** Opens the metrics window at this posthoc run. Posthoc calibration has no tracker run, so only mocap reports timing. */
export default function PipelineMetricsEntry({ group }: { group: Pick<PipelineGroup, "pipelineType" | "basePipelineId"> }) {
  if (group.pipelineType !== PipelineType.MOCAP) return null;
  return (
    <IconButton
      title="Open metrics"
      icon="externallink-icon"
      className="icon-size-25 p-01"
      onClick={() => void openPipelineMetricsWindow(`posthoc:${group.basePipelineId}`)}
      tooltip={true}
      tooltipText="Open metrics"
    />
  );
}
