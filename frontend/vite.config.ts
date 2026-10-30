import { defineConfig } from 'vitest/config';
export default defineConfig({test:{environment:'happy-dom',include:['src/**/*.test.{ts,tsx}'],restoreMocks:true},build:{sourcemap:false}});
