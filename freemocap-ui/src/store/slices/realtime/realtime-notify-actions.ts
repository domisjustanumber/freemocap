import {createAction} from '@reduxjs/toolkit';

export const realtimeApplyBlocked = createAction<{message: string}>('realtime/applyBlocked');
export const realtimeApplyBlockedDismissed = createAction('realtime/applyBlockedDismissed');
export const pipelineErrorDismissed = createAction('realtime/pipelineErrorDismissed');
export const realtimePipelineRestartRequired = createAction<{message: string}>('realtime/restartRequired');
export const realtimePipelineRestartRequiredDismissed = createAction('realtime/restartRequiredDismissed');
