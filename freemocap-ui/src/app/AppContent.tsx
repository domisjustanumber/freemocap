import * as React from 'react';
import { HashRouter } from 'react-router-dom';
import { BasePanelLayout } from "@/layout/BasePanelLayout";
import { useAppDispatch, useAppSelector } from "@/store";
import { BaseContentRouter } from "@/layout/content/BaseContentRouter";
import { UpdateBanner } from "@/components/ui-components/UpdateBanner";
import PipelineProgressSnackbar from "@/components/pipeline-progress/PipelineProgressSnackbar";
import { AutoUpdateProvider } from "@/hooks/AutoUpdateContext";
import { PlaybackProvider } from "@/components/playback/PlaybackContext";
import { useTranslation } from "react-i18next";
import { getLocaleDirection } from "@/i18n";
import { fetchAllRecordings } from "@/store/slices/recording-status/recording-status-thunks";
import { WelcomeModal } from "@/components/ui-components/WelcomeModal";
import { SettingsModal } from "@/components/ui-components/SettingsModal";
import { CertificationDialog } from "@/components/certification/CertificationDialog";
import { appLocked } from "@/services/server/full-benchmark";
import { TutorialProvider, TourController } from "@/components/tutorial";

const WELCOME_SESSION_KEY = 'freemocap.welcomeShown';

export const AppContent = function () {
    const { i18n } = useTranslation();
    const dispatch = useAppDispatch();
    const direction = getLocaleDirection(i18n.language);
    const [welcomeOpen, setWelcomeOpen] = React.useState(() => sessionStorage.getItem(WELCOME_SESSION_KEY) === null);
    React.useEffect(() => {sessionStorage.setItem(WELCOME_SESSION_KEY, 'true');}, []);
    const [settingsOpen, setSettingsOpen] = React.useState(false);

    // The native menu's "Settings…" fires this event (see useMenuActions).
    React.useEffect(() => {
        const openSettings = () => setSettingsOpen(true);
        window.addEventListener('open-settings', openSettings);
        return () => window.removeEventListener('open-settings', openSettings);
    }, []);
    // The Certification button and a failure's "File report" fire this event (see openCertification).
    const [certificationOpen, setCertificationOpen] = React.useState(false);
    React.useEffect(() => {
        const openCertification = () => setCertificationOpen(true);
        window.addEventListener('open-certification', openCertification);
        return () => window.removeEventListener('open-certification', openCertification);
    }, []);
    const closeCertification = React.useCallback(() => setCertificationOpen(false), []);
    // While the server says the start check is needed the dialog stays open with no dismiss (decision 14); it stays
    // open after the check ends, so its results show until the person closes it.
    // A running full benchmark locks the app the same way, until it ends or a cancel is asked.
    const locked = useAppSelector(state => appLocked(state.connection.certification));
    React.useEffect(() => { if (locked) setCertificationOpen(true); }, [locked]);

    React.useEffect(() => {
        document.documentElement.dir = direction;
        document.documentElement.lang = i18n.language;
    }, [direction, i18n.language]);

    React.useEffect(() => {
        dispatch(fetchAllRecordings());
    }, [dispatch]);

    return (
        <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <AutoUpdateProvider>
                <TutorialProvider>
                    <PlaybackProvider>
                        {/* The lock blocks keyboard focus too: everything but the dialog is inert. */}
                        <div inert={locked}>
                            <BasePanelLayout onOpenWelcome={() => setWelcomeOpen(true)}>
                                <BaseContentRouter />
                            </BasePanelLayout>
                            {/* Not under the Certification dialog: a first launch shows it once the dialog is closed. */}
                            <WelcomeModal open={welcomeOpen && !certificationOpen && !locked} onClose={() => setWelcomeOpen(false)} />
                            <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
                        </div>
                        <CertificationDialog open={certificationOpen || locked} onClose={closeCertification} required={locked} />
                        <TourController />
                    </PlaybackProvider>
                </TutorialProvider>
                <UpdateBanner />
                <PipelineProgressSnackbar />
            </AutoUpdateProvider>
        </HashRouter>
    );
}
