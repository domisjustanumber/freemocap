// Run from freemocap-ui: node --test electron/main/services/pipeline-metrics-window.test.cjs
// Runs the real window service with stand-ins for Electron and the file system; no window opens and nothing is written.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {transformSync} = require('esbuild');

const code = transformSync(readFileSync(path.join(__dirname, 'pipeline-metrics-window.ts'), 'utf8'),
    {loader: 'ts', platform: 'node', format: 'cjs'}).code;

test('Save snapshot offers a PNG named in local time in Downloads and writes the captured page where the person picks', async () => {
    const NOW = Date.UTC(2026, 10, 21, 19, 30, 5);  // 14:30:05 at UTC-5
    class FixedDate extends Date {
        constructor(...args) { super(...(args.length ? args : [NOW])); }
        static now() { return NOW; }
        getTimezoneOffset() { return 300; }
    }
    const windows = [], dialogs = [], writes = [];
    class BrowserWindow {
        constructor(options) {
            this.options = options;
            this.webContents = {
                setWindowOpenHandler: handler => { this.openHandler = handler; },
                on() {},
                capturePage: async () => ({toPNG: () => Buffer.from('png-bytes')}),
            };
            windows.push(this);
        }
        on() {} once() {} loadFile() {} loadURL() {} isDestroyed() { return false; }
    }
    const stubs = {
        electron: {
            app: {getPath: name => name === 'downloads' ? 'C:\\Users\\<you>\\Downloads' : assert.fail(name)},
            BrowserWindow,
            dialog: {showSaveDialog: async (window, options) => {
                dialogs.push(options);
                return {canceled: false, filePath: 'D:\\picked\\metrics.png'};
            }},
            shell: {openExternal: async () => {}},
        },
        'node:fs': {promises: {writeFile: async (file, data) => { writes.push([file, data.toString()]); }}},
        '../index': {APP_ENVIRONMENT: {IS_DEV: false}},
        '../app-paths': {APP_PATHS: {FREEMOCAP_ICON_PATH: 'icon.png', RENDERER_HTML: 'index.html'}},
        './window-manager': {WindowManager: {getMainWindow: () => null}},
    };
    const module = {exports: {}};
    vm.runInNewContext(code, {module, exports: module.exports, console, URLSearchParams, Date: FixedDate,
        require: name => stubs[name] ?? require(name)});
    module.exports.openPipelineMetricsWindow();
    assert.equal(windows[0].openHandler({url: 'freemocap-snapshot:pipeline-metrics'}).action, 'deny');
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(dialogs[0].defaultPath, path.join('C:\\Users\\<you>\\Downloads', 'pipeline-metrics-20261121-143005.png'));
    assert.equal(JSON.stringify(dialogs[0].filters), '[{"name":"PNG image","extensions":["png"]}]');  // made in the vm's realm
    assert.deepEqual(writes, [['D:\\picked\\metrics.png', 'png-bytes']]);
});
