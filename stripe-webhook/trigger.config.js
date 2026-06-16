import { defineConfig } from "@trigger.dev/sdk/v3";

export default defineConfig({
  // Replace with your project ID from trigger.dev dashboard
  // e.g. "proj_abc123xyz"
  project: "REPLACE_WITH_YOUR_PROJECT_ID",
  dirs: ["./trigger"],
  retries: {
    enabledInDev: true,
    default: {
      maxAttempts: 3,
      minTimeoutInMs: 5000,
      maxTimeoutInMs: 30000,
      factor: 2,
    },
  },
});
