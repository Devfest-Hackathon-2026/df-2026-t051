import { defineConfig } from '@playwright/test';
const python=process.platform==='win32'?'"../.venv/Scripts/python.exe"':'../.venv/bin/python';
export default defineConfig({testDir:'./tests',testMatch:'**/*.spec.ts', use:{baseURL:'http://127.0.0.1:5174'},
  webServer:[
    {command:`${python} -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 18000`,url:'http://127.0.0.1:18000/api/health',env:{APP_ENV:'local',LOCAL_DEMO:'true',IMAGE_BUCKET:'',FIRESTORE_PROJECT_ID:'',AUTH_MODE:'firebase'},reuseExistingServer:false},
    {command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort',url:'http://127.0.0.1:5174',env:{CHARTBRIDGE_API_TARGET:'http://127.0.0.1:18000'},reuseExistingServer:false},
  ],
  reporter:'list'});
