import React from 'react';
import {useTranslation} from 'react-i18next';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    realtimeApplyBlockedDismissed,
    selectRealtimeApplyBlockedMessage,
} from '@/store/slices/realtime';
import ButtonSm from '@/components/ui-components/ButtonSm';

export function RealtimeApplyBlockedToast() {
    const {t} = useTranslation();
    const dispatch = useAppDispatch();
    const blockedMessage = useAppSelector(selectRealtimeApplyBlockedMessage);

    if (!blockedMessage) return null;

    return (
        <div className="realtime-apply-blocked-toast toast-notification info flex flex-col gap-1">
            <p className="text sm">{t('realtime_atLeastOneCameraRequired')}</p>
            <ButtonSm
                text="Dismiss"
                onClick={() => dispatch(realtimeApplyBlockedDismissed())}
                className="secondary w-full"
            />
        </div>
    );
}
