import React from 'react';
import type {SystemInformation, SystemInformationState} from '@/services/server/system-information';
import type {RunTimingSnapshot} from '@/services/server/server-helpers/pipeline-timing-types';
import type {LiveLoad} from '@/services/server/transport/message-contract';
import IconButton from '@/components/ui-components/IconButton';

/** What a value the server does not know shows: never 0. */
export const MISSING = '—';

type Value = string | number | boolean | null | undefined;
const shown = (value: Value): string => value == null || value === '' ? MISSING : typeof value === 'boolean' ? (value ? 'yes' : 'no') : String(value);

const BYTE_UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
export function formatBytes(value: number | null | undefined): string {
    if (value == null) return MISSING;
    let unit = 0;
    while (Math.abs(value) >= 1024 && unit < BYTE_UNITS.length - 1) { value /= 1024; unit++; }
    return `${value.toFixed(unit === 0 ? 0 : 1)} ${BYTE_UNITS[unit]}`;
}

export function formatHz(value: number | null | undefined): string {
    if (value == null) return MISSING;
    return value >= 1e9 ? `${(value / 1e9).toFixed(2)} GHz` : value >= 1e6 ? `${(value / 1e6).toFixed(0)} MHz` : `${value} Hz`;
}

export const formatShare = (value: number | null | undefined): string => value == null ? MISSING : `${(value * 100).toFixed(0)} %`;

const muted: React.CSSProperties = {color: 'var(--gray-500)'};
const cell: React.CSSProperties = {paddingRight: 10, verticalAlign: 'top'};

function Rows({rows}: {rows: [string, React.ReactNode][]}): React.ReactElement {
    return <table className="text sm" style={{borderCollapse: 'collapse'}}><tbody>
        {rows.map(([label, value]) => <tr key={label}><td style={{...cell, ...muted}}>{label}</td><td>{value}</td></tr>)}
    </tbody></table>;
}

function Table({head, rows}: {head: string[]; rows: React.ReactNode[][]}): React.ReactElement {
    return <table className="text sm" style={{borderCollapse: 'collapse'}}>
        <thead><tr style={{...muted, textAlign: 'left'}}>{head.map(name => <th key={name} style={cell}>{name}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={index}>{row.map((value, column) => <td key={column} style={cell}>{value}</td>)}</tr>)}</tbody>
    </table>;
}

function Group({title, summary, open = true, children}: {title: string; summary?: string; open?: boolean; children: React.ReactNode}): React.ReactElement {
    return <details className="settings-disclosure" open={open} aria-label={title}>
        <summary>{title}{summary && <span className="text sm" style={{...muted, fontWeight: 400}}>{summary}</span>}</summary>
        <div style={{paddingBottom: 4}}>{children}</div>
    </details>;
}

const Errors = ({errors}: {errors: readonly string[]}) => errors.length === 0 ? null
    : <p className="text sm" style={{color: 'var(--warning-300)'}}>{errors.join(' · ')}</p>;

function HostGroup({host}: {host: SystemInformation['host']}): React.ReactElement {
    const virtual = [host.is_wsl && 'WSL', host.is_vm && `VM${host.hypervisor ? ` (${host.hypervisor})` : ''}`,
        host.container_runtime && `container (${host.container_runtime})`].filter(Boolean).join(', ');
    return <Group title="Host" summary={shown(host.cpu_name)}>
        <Rows rows={[
            ['OS', `${host.os_name} ${host.os_release} (${host.os_version}${host.os_build ? `, build ${host.os_build}` : ''})`],
            ['Architecture', host.arch],
            ['CPU', shown(host.cpu_name)],
            ['Cores', `${shown(host.cpu_physical_cores)} physical, ${shown(host.cpu_logical_cores)} logical`],
            ['Max frequency', formatHz(host.cpu_max_frequency_hz)],
            ['Memory', formatBytes(host.memory_total_bytes)],
            ['Virtualization', host.is_vm == null && !virtual ? MISSING : virtual || 'none'],
        ]}/>
        <Errors errors={host.probe_errors}/>
    </Group>;
}

function GpuGroup({gpus}: {gpus: SystemInformation['gpus']}): React.ReactElement {
    return <Group title="GPUs" summary={`${gpus.length}`}>
        {gpus.length === 0 ? <p className="text sm" style={muted}>No GPU found.</p> : <Table
            head={['Name', 'Vendor', 'Device key', 'Driver', 'VRAM', 'Compute']}
            rows={gpus.map(gpu => [shown(gpu.name), gpu.vendor, shown(gpu.device_key), shown(gpu.driver_version),
                formatBytes(gpu.vram_total_bytes), gpu.compute_capability ? `${gpu.compute_capability}${gpu.brand ? ` (${gpu.brand})` : ''}` : MISSING])}/>}
    </Group>;
}

function RuntimeGroup({runtime}: {runtime: SystemInformation['runtime']}): React.ReactElement {
    return <Group title="Runtime & libraries" summary={`skellytracker ${runtime.skellytracker_version}`} open={false}>
        <Rows rows={[
            ['Python', `${runtime.python_implementation} ${runtime.python_version} (${runtime.python_build}; ${runtime.python_compiler})`],
            ['skellytracker', `${runtime.skellytracker_version}${runtime.skellytracker_commit ? ` @ ${runtime.skellytracker_commit}` : ''}`],
            ['ONNX Runtime', `${shown(runtime.ort_version)}${runtime.ort_packages.length ? ` (${runtime.ort_packages.join(', ')})` : ''}`],
            ['ORT providers', runtime.ort_ep_names.length ? runtime.ort_ep_names.join(', ') : MISSING],
            ['MediaPipe', shown(runtime.mediapipe_version)],
            ['Driver CUDA', shown(runtime.driver_supported_cuda_version)],
            ['Loaded libraries', runtime.loaded_libraries.length
                ? runtime.loaded_libraries.map(library => `${library.name} ${shown(library.version)}`).join(', ')
                : 'none loaded yet (a GPU session loads them)'],
        ]}/>
        <Errors errors={runtime.probe_errors}/>
    </Group>;
}

function ExecutionProviderGroup({eps, gpus}: {eps: SystemInformation['execution_providers']; gpus: SystemInformation['gpus']}): React.ReactElement {
    const {recommendation} = eps;
    const gpuName = (key: string | null) => key == null ? null : gpus.find(gpu => gpu.device_key === key)?.name ?? key;
    const chosenDevice = gpuName(recommendation.chosen.device_key);
    return <Group title="Execution providers" summary={`recommended: ${recommendation.chosen.ep_key}`} open={false}>
        <Table head={['EP', 'State', 'Usable', 'Devices', 'Install']} rows={eps.providers.map(row => [
            `${row.label} (${row.key})`, row.state, shown(row.usable),
            row.devices.length ? row.devices.map(device => shown(device.name ?? device.key)).join(', ') : MISSING, shown(row.install_hint)])}/>
        <Rows rows={[
            ['Recommended', `${recommendation.chosen.ep_key}${chosenDevice ? ` on ${chosenDevice}` : ''}, ${recommendation.precision}`
                + ` (${recommendation.chosen.status}${recommendation.chosen.reason ? `: ${recommendation.chosen.reason}` : ''})`],
            ['Hardware class', recommendation.hardware_class],
            ['Skipped', recommendation.skipped.length
                ? recommendation.skipped.map(skip => `${skip.ep_key}${skip.reason ? `: ${skip.reason}` : ''}`).join(' · ') : 'none'],
            ['Offers', recommendation.offers.length ? recommendation.offers.map(offer => offer.note).join(' · ') : 'none'],
            ['ORT matches the pin', `${shown(eps.core_matches_pin)} (ONNX Runtime ${shown(eps.ort_version)})`],
        ]}/>
        <Errors errors={eps.warnings}/>
    </Group>;
}

const modelsOfRun = (info: SystemInformation, run: RunTimingSnapshot) =>
    info.runs.find(entry => entry.mode === run.mode && entry.pipeline_id === run.pipelineId);

/** The run whose models the shown answer does not list yet: they load after the run starts, so ask again. */
export function runAwaitingModels(state: SystemInformationState, run: RunTimingSnapshot | null): string | null {
    return run && state.info && !state.loading && !modelsOfRun(state.info, run)?.models.length ? run.key : null;
}

function ModelsGroup({info, run}: {info: SystemInformation; run: RunTimingSnapshot | null}): React.ReactElement {
    const models = run ? modelsOfRun(info, run) : undefined;
    return <Group title="Models of this run" summary={models?.requested_provider ? `requested EP: ${models.requested_provider}` : undefined}>
        {!run ? <p className="text sm" style={muted}>No run is selected.</p>
            : !models || models.models.length === 0
                ? <p className="text sm" style={muted}>This run reports no models yet: it has not started tracking, or runs none. This window asks again for a minute.</p>
                : <Table head={['Node', 'Model', 'Size', 'Precision', 'EP', 'Device']} rows={models.models.map(model => {
                    const keys = model.device == null ? [] : Array.isArray(model.device) ? model.device : [model.device];
                    return [model.node, `${shown(model.key)}${model.version ? ` ${model.version}` : ''}${model.engine ? ` (${model.engine})` : ''}`,
                        shown(model.size), shown(model.precision), shown(model.execution_provider),
                        keys.length ? keys.map((key, index) => model.device_names?.[index] ?? key).join(', ') : MISSING];
                })}/>}
    </Group>;
}

export function LiveLoadGroup({load}: {load: LiveLoad | null}): React.ReactElement {
    return <Group title="Live load" summary={load ? `every ${load.interval_s} s` : undefined}>
        {!load ? <p className="text sm" style={muted}>
            Live load comes with the pipeline timing messages, so it needs a pipeline: start real-time processing or process a recording.
        </p> : <>
            <Rows rows={[
                ['CPU (all cores)', formatShare(load.cpu_utilization)],
                ['Memory', `${formatBytes(load.memory_used_bytes)} used, ${formatBytes(load.memory_available_bytes)} available`],
                ['Backend process', `CPU ${formatShare(load.process_cpu_utilization)}, RAM ${formatBytes(load.process_rss_bytes)}, VRAM ${formatBytes(load.process_vram_used_bytes)}`],
            ]}/>
            {load.gpus.length > 0 && <Table head={['GPU', 'Load', 'VRAM used', 'VRAM free', 'Backend VRAM']} rows={load.gpus.map(gpu => [
                shown(gpu.name ?? gpu.device_key), formatShare(gpu.utilization), formatBytes(gpu.vram_used_bytes),
                formatBytes(gpu.vram_free_bytes), formatBytes(gpu.process_vram_used_bytes)])}/>}
            <Errors errors={load.sample_errors}/>
        </>}
    </Group>;
}

/** The top panel of the metrics window: skellytracker's system information and the newest live load. */
export function SystemInformationPanel({state, run, liveLoad, connected, onRefresh}: {state: SystemInformationState; run: RunTimingSnapshot | null;
    liveLoad: LiveLoad | null; connected: boolean; onRefresh: () => void}): React.ReactElement {
    const {info} = state;
    return <section aria-label="System information" data-slot="system-information"
        style={{padding: '2px 8px 4px', borderBottom: '1px solid var(--gray-700)', maxHeight: '45vh', overflowY: 'auto'}}>
        <div className="flex flex-row items-center gap-2">
            <span className="text md">System information</span>
            <span className="text sm" style={state.error ? {color: 'var(--warning-300)'} : muted}>
                {!connected ? 'Not connected' : state.loading ? 'Loading…' : state.error ? `Could not load: ${state.error}` : ''}
            </span>
            <div className="flex-1"/>
            <IconButton icon="loop-icon" title="Refresh system information" onClick={onRefresh}/>
        </div>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', columnGap: 16}}>
            {info && <>
                <HostGroup host={info.host}/>
                <GpuGroup gpus={info.gpus}/>
                <RuntimeGroup runtime={info.runtime}/>
                <ExecutionProviderGroup eps={info.execution_providers} gpus={info.gpus}/>
                <ModelsGroup info={info} run={run}/>
            </>}
            <LiveLoadGroup load={liveLoad}/>
        </div>
    </section>;
}
