import React from 'react';
import {Provider} from 'react-redux';
import {store} from '@/store';
import {ServerContextProvider} from "@/services/server/ServerContextProvider";
import {AppContent} from "@/app/AppContent";
import PipelineMetricsWindowPage from "@/components/pipeline-metrics/PipelineMetricsWindowPage";
import {PIPELINE_METRICS_HASH} from "@/services/electron-ipc/open-pipeline-metrics-window";


function App() {
    // The pipeline metrics window loads this page at its own hash and holds its own transport client.
    if (window.location.hash.startsWith(PIPELINE_METRICS_HASH)) return <PipelineMetricsWindowPage/>;
    return (
        <Provider store={store}>
            <ServerContextProvider>
                <AppContent/>
            </ServerContextProvider>
        </Provider>
    );
}

export default App;
