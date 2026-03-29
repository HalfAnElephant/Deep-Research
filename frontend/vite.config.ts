import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("/zrender/")) return "vendor-zrender";
          if (id.includes("/echarts/")) return "vendor-echarts";
          if (id.includes("/cytoscape-dagre/") || id.includes("/dagre/")) return "vendor-dagre";
          if (id.includes("/cytoscape/")) return "vendor-cytoscape";
          if (id.includes("/react-markdown/")) return "vendor-markdown";
          if (id.includes("/react/") || id.includes("/react-dom/")) return "vendor-react";
          return undefined;
        }
      }
    }
  },
  server: {
    port: 5174
  }
});
