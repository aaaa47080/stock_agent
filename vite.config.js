import { defineConfig } from 'vite';

export default defineConfig({
    root: 'web',
    base: '/',
    build: {
        outDir: '../dist/static',
        emptyOutDir: false,
        sourcemap: true,
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
