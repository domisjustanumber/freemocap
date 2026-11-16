import {createListenerMiddleware} from '@reduxjs/toolkit';
import type {RootState} from './root-state-types';
import {serverUrls} from '@/constants/server-urls';
import {requestExecutionProviderSuggestion} from '@/services/server/execution-providers';
import {legacyExecutionProviderResolved} from './slices/mocap/mocap-slice';

/** Asks the connected server for the replacement of a pending legacy EP key, again after each reconnect. */
export const legacyExecutionProviderListenerMiddleware = createListenerMiddleware();
const startListening = legacyExecutionProviderListenerMiddleware.startListening.withTypes<RootState>();

startListening({
    predicate: (_, curr, prev) => curr.mocap.executionProviderMigration?.status === 'pending' && curr.connection.isConnected
        && (!prev.connection.isConnected || prev.connection.serverPid !== curr.connection.serverPid
            || prev.mocap.executionProviderMigration !== curr.mocap.executionProviderMigration),
    effect: async (_, api) => {
        api.cancelActiveListeners();
        const migration = api.getState().mocap.executionProviderMigration;
        if (migration?.status !== 'pending') return;
        try {
            const suggested = await requestExecutionProviderSuggestion(serverUrls.getHttpUrl(), migration.saved, api.signal);
            api.dispatch(legacyExecutionProviderResolved({saved: migration.saved, suggested}));
        } catch (error) {
            if (!api.signal.aborted) console.warn('Could not ask the server for the replacement of a saved EP key:', error);
        }
    },
});
