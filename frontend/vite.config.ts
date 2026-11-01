import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // In Docker Compose the API is reachable as http://api:8000.
    proxy: { '/api': process.env.API_TARGET ?? 'http://localhost:8000' },
  },
});
