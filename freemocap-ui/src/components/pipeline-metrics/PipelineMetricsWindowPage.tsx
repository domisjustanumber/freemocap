import React, {useEffect, useMemo, useRef, useState} from 'react';
import {PipelineNetworkTimeline} from '@/components/pipeline-metrics/PipelineNetworkTimeline';
import {buildTimelineViewModel} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {stageLabel, timingEngine} from '@/components/pipeline-metrics/pipelineTaskTopology';
import {metricsState, type MetricsState, requestedRunKey, runLabel, sortStages} from '@/components/pipeline-metrics/pipelineMetricsState';
import {feedPipelineTimingStore, PipelineTimingStore} from '@/services/server/server-helpers/pipeline-timing-store';
import {PIPELINE_TIMELINE_FRAME_WINDOW, type RunTimingSnapshot} from '@/services/server/server-helpers/pipeline-timing-types';
import {ConnectionState} from '@/services/server/server-helpers/websocket-connection';
import {TransportService} from '@/services/server/transport/TransportService';
import {DEFAULT_HOST, DEFAULT_PORT, serverUrls} from '@/constants/server-urls';
import {loadFromStorage, STORAGE_KEYS} from '@/components/control-panels/server-connection/storage';
import IconButton from '@/components/ui-components/IconButton';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import {runAwaitingModels, SystemInformationPanel} from '@/components/pipeline-metrics/SystemInformationPanel';
import {requestSystemInformation, type SystemInformationState, watchSystemInformation} from '@/services/server/system-information';

const POLL_MS = 250;
// A run's models load after it starts; the window asks again this often, for about a minute per run.
const MODELS_RETRY_MS = 2000, MODELS_RETRIES = 30;

const STATE_TEXT: Record<Exclude<MetricsState, 'ready' | 'timing-disabled'>, string> = {
    'disconnected': 'Not connected to the FreeMoCap server. This window reconnects on its own.',
    'no-pipeline': 'No pipeline is reporting timing. Start real-time processing or process a recording in the main window.',
    'not-running': 'This pipeline is not running.',
};

const TURN_ON = 'To turn it on: in the main window, click the gear next to the Real-time processing button and switch on "Log pipeline times" (it is off by default and saved).';

/** What the window says when the chosen run started with timing off, and exactly how to turn it on. */
export const TIMING_OFF_TEXT: Record<RunTimingSnapshot['mode'], string> = {
    realtime: `Pipeline timing is off for this real-time pipeline, so it sends no task events. ${TURN_ON} `
        + 'Then stop and start Real-time processing (click it twice): a running pipeline keeps the setting it started with.',
    posthoc: `Pipeline timing was off when this recording started processing, so it sends no task events. ${TURN_ON} `
        + 'The next recording you process is timed; a run keeps the setting it started with.',
};

export function StateNotice({state, run}: {state: Exclude<MetricsState, 'ready'>; run: RunTimingSnapshot | null}): React.ReactElement {
    return <p className="text md" style={{margin: 8, padding: '8px 12px', borderRadius: 4, backgroundColor: 'var(--gray-800)',
        borderLeft: `3px solid ${state === 'timing-disabled' ? 'var(--warning-400)' : 'var(--green-500)'}`}}>
        {state === 'timing-disabled' ? TIMING_OFF_TEXT[run?.mode ?? 'realtime'] : STATE_TEXT[state]}
    </p>;
}

const ms = (value: number) => value.toFixed(value >= 100 ? 0 : 1);

// Measured on skellytracker 0a50c719 (pipeline-metrics-port-plan.md, PM state): CPU within noise, cuda 0.0 %, trt-rtx +0.08 ms.
const SPAN_COST = 'Its spans cost under 0.1 ms per frame (within noise on CPU).';

// The main window saves its server address in storage this window shares.
function applySavedServer(): void {
    serverUrls.setHost(loadFromStorage(STORAGE_KEYS.SERVER_HOST, DEFAULT_HOST));
    serverUrls.setPort(loadFromStorage(STORAGE_KEYS.SERVER_PORT, DEFAULT_PORT));
}

export default function PipelineMetricsWindowPage(): React.ReactElement {
    const [store] = useState(() => new PipelineTimingStore());
    const [connected, setConnected] = useState(false);
    const [runs, setRuns] = useState<RunTimingSnapshot[]>([]);
    const [selectedKey, setSelectedKey] = useState<string | null>(() => requestedRunKey(window.location.hash));
    const [frozen, setFrozen] = useState<RunTimingSnapshot | null>(null);
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [systemInformation, setSystemInformation] = useState<SystemInformationState>({info: null, loading: false, error: null});
    const refreshSystemInformation = useRef<() => void>(() => {});

    // The page's own title would otherwise name the window "FreeMoCap".
    useEffect(() => { document.title = 'FreeMoCap pipeline metrics'; }, []);

    // An opener that names a run (a posthoc card's "Open metrics") switches an open window to it.
    useEffect(() => {
        const onHash = () => {
            const key = requestedRunKey(window.location.hash);
            if (key) { setSelectedKey(key); setFrozen(null); }
        };
        window.addEventListener('hashchange', onHash);
        return () => window.removeEventListener('hashchange', onHash);
    }, []);

    // One more transport client, like the main window: it reconnects by itself and asks for timing on every connect.
    useEffect(() => {
        applySavedServer();
        // It draws no camera images, so it declines frames: the server then skips their JPEG, compose and encode work.
        const transport = new TransportService({url: serverUrls.getWebSocketUrl(), frames: false});
        const onState = (state: ConnectionState) => setConnected(state === ConnectionState.CONNECTED);
        transport.on('state-change', onState);
        const stopFeed = feedPipelineTimingStore(transport, store);
        // The static groups: fetched on every connect (a restarted or another server answers for itself) and on refresh.
        const systemWatch = watchSystemInformation(transport, signal => requestSystemInformation(serverUrls.getHttpUrl(), signal), setSystemInformation);
        refreshSystemInformation.current = systemWatch.refresh;
        const onStorage = (event: StorageEvent) => {
            if (event.key !== STORAGE_KEYS.SERVER_HOST && event.key !== STORAGE_KEYS.SERVER_PORT) return;
            applySavedServer();
            transport.updateUrl(serverUrls.getWebSocketUrl());
            transport.disconnect();
            transport.connect();
        };
        window.addEventListener('storage', onStorage);
        transport.connect();
        const poll = setInterval(() => setRuns(store.runs()), POLL_MS);
        return () => {
            clearInterval(poll);
            window.removeEventListener('storage', onStorage);
            stopFeed();
            systemWatch.stop();
            transport.off('state-change', onState);
            transport.disconnect();
        };
    }, [store]);

    const live = runs.find(run => run.key === selectedKey) ?? runs[0] ?? null;
    const run = frozen ?? live;
    const state = metricsState(connected, run);
    const awaitingModels = runAwaitingModels(systemInformation, run);
    const modelRetries = useRef(new Map<string, number>());
    useEffect(() => {
        const attempts = awaitingModels ? modelRetries.current.get(awaitingModels) ?? 0 : MODELS_RETRIES;
        if (!awaitingModels || attempts >= MODELS_RETRIES) return;
        const timer = setTimeout(() => {
            modelRetries.current.set(awaitingModels, attempts + 1);
            refreshSystemInformation.current();
        }, MODELS_RETRY_MS);
        return () => clearTimeout(timer);
    }, [awaitingModels, systemInformation]);
    const model = useMemo(() => buildTimelineViewModel({
        events: run?.events ?? [], configuredCameraFpsHz: run?.configuredCameraFpsHz ?? null, incompleteFrames: run?.incompleteFrames,
    }), [run]);

    return (
        <div style={{height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--gray-900)', color: 'var(--gray-300)'}}>
            <div className="flex flex-row items-center gap-2 flex-wrap" style={{padding: '4px 8px', borderBottom: '1px solid var(--gray-700)'}}>
                <span className="title">Pipeline metrics</span>
                <span className="text md" style={{color: connected ? 'var(--green-300)' : 'var(--gray-400)'}}>
                    {connected ? 'Connected' : 'Not connected'}
                </span>
                <div className="flex-1"/>
                {runs.length > 0 && <SettingSelectInput label="Pipeline run" value={live?.key ?? ''} disabled={frozen != null}
                    options={runs.map(option => ({label: runLabel(option), value: option.key}))} onChange={setSelectedKey}/>}
                <IconButton icon={frozen ? 'play-icon' : 'pause-icon'} title={frozen ? 'Resume' : 'Pause'}
                    onClick={() => setFrozen(frozen ? null : live)}/>
            </div>

            {/* Host, GPUs, runtime, execution providers, models of the selected run and live load (pipeline-metrics-port-plan.md §5). */}
            <SystemInformationPanel state={systemInformation} run={run} connected={connected}
                liveLoad={runs.find(entry => entry.liveLoad)?.liveLoad ?? null} onRefresh={() => refreshSystemInformation.current()}/>

            {state !== 'ready' || !run
                ? <StateNotice state={state as Exclude<MetricsState, 'ready'>} run={run}/>
                : <RunSummary run={run}/>}

            {state === 'ready' && (
                <div style={{flex: 1, minHeight: 0, margin: '0 8px 8px', border: '1px solid var(--gray-700)', borderRadius: 4, overflow: 'hidden'}}>
                    <PipelineNetworkTimeline model={model} selectedTaskId={selectedTaskId} onSelectTask={setSelectedTaskId}/>
                </div>
            )}
        </div>
    );
}

export function RunSummary({run}: {run: RunTimingSnapshot}): React.ReactElement {
    const lag = Object.entries(run.nodeLag);
    return (
        <div className="flex flex-col gap-1" style={{padding: '4px 8px'}}>
            <p className="text sm" style={{color: 'var(--warning-300)'}}>
                {run.mode === 'realtime'
                    ? `Timing is on for this pipeline (log_pipeline_times). ${SPAN_COST}`
                    : `Timing is on for the whole posthoc run. ${SPAN_COST}`}
            </p>
            <p className="text md">
                {run.endToEnd
                    ? <>End-to-end per complete frame: <strong>{ms(run.endToEnd.meanMs)} ms</strong> mean
                        (range {ms(run.endToEnd.minMs)}–{ms(run.endToEnd.maxMs)} ms, {run.endToEnd.frames} frames)</>
                    : 'Waiting for a complete frame…'}
            </p>
            <p className="text sm" style={{color: 'var(--gray-500)'}}>
                From each frame's own events: its first event start to its last event end. Frames are sampled about four times a second.
            </p>
            <p className="text sm" style={{color: 'var(--gray-400)'}}>
                {run.mode === 'realtime'
                    ? `Dropped timing events: ${run.droppedInLastMessage} in the newest message, ${run.droppedSinceOpened} since this window opened.`
                    : 'Dropped timing events are not counted for a posthoc run: its buffer drops its oldest records silently while nothing reads them.'}
                {run.incompleteFrames.length > 0 && <span style={{color: 'var(--warning-400)'}}> · {run.incompleteFrames.length} incomplete frame(s)</span>}
                {/* Lag and stall follow the camera rate; a posthoc run reads its videos as fast as it tracks. */}
                {run.mode === 'realtime' && lag.map(([kind, frames]) => <span key={kind} style={{color: frames <= 3 ? 'var(--warning-300)' : 'var(--red-300)'}}> · {kind} +{frames}</span>)}
                {run.mode === 'realtime' && run.staleNodes.length > 0 && <span style={{color: 'var(--red-400)'}}> · stalled: {run.staleNodes.join(', ')}</span>}
            </p>
            {run.stages.length > 0 && <table className="text sm" style={{borderCollapse: 'collapse', maxWidth: 760}}>
                <thead>
                    <tr style={{color: 'var(--gray-500)', textAlign: 'left'}}>
                        <th>Stage</th><th>Engine</th><th style={{textAlign: 'right'}}>ms/frame</th><th style={{textAlign: 'right'}}>FPS</th>
                        <th style={{textAlign: 'right'}}>range (ms)</th><th style={{textAlign: 'right'}}>frames</th>
                    </tr>
                </thead>
                <tbody>
                    {sortStages(run.stages).map(stage => (
                        <tr key={stage.sourceKey}>
                            <td style={{paddingRight: 12}}>{stageLabel(stage.sourceKey, stage.stage, stage.cameraId)}</td>
                            <td>{timingEngine(stage) ?? 'freemocap'}</td>
                            <td style={{textAlign: 'right'}}>{ms(stage.meanMs)}</td>
                            <td style={{textAlign: 'right'}}>{stage.fps.toFixed(1)}</td>
                            <td style={{textAlign: 'right'}}>{ms(stage.minMs)}–{ms(stage.maxMs)}</td>
                            <td style={{textAlign: 'right'}}>{stage.frames}</td>
                        </tr>
                    ))}
                </tbody>
            </table>}
            <p className="text sm" style={{color: 'var(--gray-500)'}}>
                FPS is 1000 ÷ the stage's mean ms/frame: the rate that stage alone would allow, not the pipeline's frame rate.
                The timeline shows the newest {PIPELINE_TIMELINE_FRAME_WINDOW} frames.
            </p>
        </div>
    );
}
