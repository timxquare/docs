#!/usr/bin/env node
// Entry point. Usage:
//   node index.mjs            -> dry run (safe, writes nothing)
//   node index.mjs --inspect  -> probe PromoteKit and print data shapes
//   node index.mjs --live     -> actually migrate into Tolt
//   node index.mjs --live --limit 5   -> live, but only first 5 affiliates
//   node index.mjs --reset    -> ignore saved progress and start over

import { run } from "./src/migrate.mjs";
import { log } from "./src/util.mjs";

run().catch((err) => {
  log.error(err.stack || err.message || String(err));
  process.exit(1);
});
