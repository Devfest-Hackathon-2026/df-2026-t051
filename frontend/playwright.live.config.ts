import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./live-tests',outputDir:'./test-results-live',use:{baseURL:process.env.CHARTBRIDGE_LIVE_URL ?? 'http://127.0.0.1:8085',actionTimeout:15000},reporter:'list',workers:1});
