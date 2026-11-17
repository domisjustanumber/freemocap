import {BrowserWindow, shell} from 'electron';
import {APP_ENVIRONMENT} from '../index';
import {APP_PATHS} from '../app-paths';
import {WindowManager} from './window-manager';

let metricsWindow: BrowserWindow | null = null;

/** Open the pipeline metrics page in its own window, or focus the one already open.
 *  `pipeline` (`mode:pipeline_id`) selects that run, also in a window already open. */
export function openPipelineMetricsWindow(pipeline?: string): void {
    const hash = pipeline ? `/pipeline-metrics?${new URLSearchParams({pipeline})}` : '/pipeline-metrics';
    if (metricsWindow && !metricsWindow.isDestroyed()) {
        if (metricsWindow.isMinimized()) metricsWindow.restore();
        // A hash change keeps the page and its statistics; the page switches its run on hashchange.
        // The same hash again fires no hashchange (the user picked another run since), so send one.
        if (pipeline) void metricsWindow.webContents.executeJavaScript(`{const hash = ${JSON.stringify('#' + hash)};
            if (location.hash === hash) dispatchEvent(new HashChangeEvent('hashchange')); else location.hash = hash;}`);
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
        window.loadURL(`${APP_ENVIRONMENT.VITE_DEV_SERVER_URL}#${hash}`);
    } else {
        window.loadFile(APP_PATHS.RENDERER_HTML, {hash});
    }
}
