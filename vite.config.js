import { defineConfig } from 'vite';

export default defineConfig({
    root: 'web',
    base: '/static/',
    build: {
        outDir: '../dist/static',
        emptyOutDir: false,
        sourcemap: true,
        chunkSizeWarningLimit: 800,
    },
    server: {
        proxy: {
            '/api': 'http://localhost:8080',
            '/ws': {
                target: 'ws://localhost:8080',
                ws: true,
            },
            '/static': 'http://localhost:8080',
        },
    },
});
