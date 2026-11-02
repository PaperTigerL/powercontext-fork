import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  root: 'web',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/models': 'http://127.0.0.1:8787',
    },
  },
  optimizeDeps: {
    // onnxruntime-web 体积大且含 wasm，排除出预构建由运行时按需加载
    exclude: ['onnxruntime-web'],
  },
});