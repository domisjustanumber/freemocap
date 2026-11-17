import {BrowserWindow, shell} from 'electron';
import {APP_ENVIRONMENT} from '../index';
import {APP_PATHS} from '../app-paths';
import {WindowManager} from './window-manager';

let metricsWindow: BrowserWindow | null = null;

/** Open the pipeline metrics page in its own window, or focus the one already open. */
export function openPipelineMetricsWindow(): void {
    if (metricsWindow && !metricsWindow.isDestroyed()) {
        if (metricsWindow.isMinimized()) metricsWindow.restore();
        metricsWindow.focus();
        return;
    }
    const window = new BrowserWindow({
        title: 'FreeMoCap pipeline metrics',
        icon: APP_PATHS.FREEMOCAP_ICON_PATH,
        // A child window closes with the main window, so the app still quits when the main window closes.
        parent: WindowManager.getMainWindow() ?? undefined,
        width: 1100,
        height: 760,
        minWidth: 640,
        minHeight: 400,
        // The page needs no preload: it reaches the server over its own websocket like the main window.
        webPreferences: {contextIsolation: true, nodeIntegration: false, sandbox: true},
        show: false,
    });
    metricsWindow = window;
    window.on('closed', () => { metricsWindow = null; });
    window.once('ready-to-show', () => window.show());
    window.webContents.setWindowOpenHandler(({url}) => {
        if (url.startsWith('http:') || url.startsWith('https:')) {
            shell.openExternal(url).catch(error => console.error('Failed to open external link:', error));
        }
        return {action: 'deny'};
    });
    // The page never navigates; a dropped file would otherwise replace it.
    window.webContents.on('will-navigate', event => event.preventDefault());

    if (APP_ENVIRONMENT.IS_DEV && APP_ENVIRONMENT.VITE_DEV_SERVER_URL) {
        window.loadURL(`${APP_ENVIRONMENT.VITE_DEV_SERVER_URL}#/pipeline-metrics`);
    } else {
        window.loadFile(APP_PATHS.RENDERER_HTML, {hash: '/pipeline-metrics'});
    }
}
