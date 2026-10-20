import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const shared = fileURLToPath(new URL('../shared', import.meta.url));

export default defineConfig({
    plugins: [react()],
    resolve: { alias: { '@shared': shared } },
    server: { port: 5175, fs: { allow: ['..'] } },
    preview: { port: 4175 },
});
