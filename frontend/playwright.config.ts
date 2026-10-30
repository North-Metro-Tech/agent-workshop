import {defineConfig} from '@playwright/test';
// Run against the actual loopback Workshop service, never a mocked API.
// Provision WORKSHOP_E2E_TOKEN only in the test process environment; never VITE_*.
export default defineConfig({testDir:'./e2e',fullyParallel:false,workers:1,use:{baseURL:process.env.WORKSHOP_E2E_URL??'http://127.0.0.1:8765',headless:true,launchOptions:{executablePath:process.env.WORKSHOP_E2E_CHROMIUM},trace:'off',screenshot:'off',video:'off'},reporter:'list'});
