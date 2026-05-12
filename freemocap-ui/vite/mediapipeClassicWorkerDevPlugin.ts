import path from 'node:path'
import esbuild from 'esbuild'
import type {Plugin} from 'vite'

/**
 * Dev-only: Vite's classic worker URLs (`worker_file&type=classic`) only prepend env via
 * `importScripts`; the worker body stays as transformed ESM with `import` statements, which
 * classic workers cannot run. Production uses Rollup (`bundleWorkerEntry`); this mirrors that with
 * esbuild as a late transform replacement.
 *
 * Runs as `enforce: 'post'` so it replaces Vite's output for these module ids (Windows paths OK).
 */
export function mediapipeClassicWorkerDevPlugin(): Plugin {
    let viteBase = '/'
    let workspaceRoot = ''

    return {
        name: 'freemocap:mediapipe-classic-worker-dev',
        apply: 'serve',
        enforce: 'post',
        configResolved(config) {
            viteBase = config.base
            workspaceRoot = config.root
        },
        transform: async function mediapipeWorkerClassicBundle(_source, id) {
            const normId = id.replace(/\\/g, '/')
            if (
                !normId.includes('mediapipe-engine.worker.ts') ||
                !normId.includes('worker_file') ||
                !normId.includes('type=classic')
            ) {
                return
            }

            const aliasAtSrc = path.join(workspaceRoot, 'src')
            const entry = path.join(workspaceRoot, 'src/services/realtime-mediapipe/mediapipe-engine.worker.ts')
            this.addWatchFile(entry)

            const bundle = await esbuild.build({
                absWorkingDir: workspaceRoot,
                entryPoints: [entry],
                bundle: true,
                format: 'iife',
                platform: 'browser',
                target: ['es2022'],
                legalComments: 'none',
                logLevel: 'silent',
                write: false,
                alias: {
                    '@': aliasAtSrc,
                },
            })

            // Esbuild emits the in-memory bundle as virtual path `<stdout>` (not "*.js").
            const out = bundle.outputFiles?.find(
                (f) => typeof f.text === 'string' && !String(f.path).endsWith('.map'),
            )
            if (!out) {
                this.error(
                    `[mediapipe worker dev] esbuild produced no JS for ${entry}; outputFiles=` +
                        (bundle.outputFiles?.map((f) => f.path).join(', ') || '(none)'),
                )
            }

            const envUrl = JSON.stringify(path.posix.join(viteBase, '/@vite/env'))
            const code = `importScripts(${envUrl});\n${out.text}`
            return {code, map: {mappings: ''}}
        },
    }
}
