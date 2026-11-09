import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./audit-tests',outputDir:'./test-results-audit',workers:1,retries:0,reporter:'list',use:{baseURL:process.env.CHARTBRIDGE_LIVE_URL,actionTimeout:15000,trace:'off',screenshot:'off',video:'off'}});
