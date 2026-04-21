import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // During local dev (npm run dev), proxy API calls to FastAPI
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
// import { defineConfig } from "vite";
// import react from "@vitejs/plugin-react";
 
// export default defineConfig({
//   plugins: [react()],
//   server: {
//     host: true,   // needed so Vite listens on 0.0.0.0 inside Docker
//     port: 5173,
//     proxy: {
//       // In dev, proxy API and WebSocket directly to FastAPI
//       "/api": "http://dashboard:8000",
//       "/ws":  { target: "ws://dashboard:8000", ws: true },
//     },
//   },
// });
 