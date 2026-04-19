#!/usr/bin/env node
// SPDX-License-Identifier: MIT
'use strict';
const { main } = require('../lib/cli');
const exitCode = main(process.argv.slice(2));

// Node's process.stdout.write() returns false when the OS pipe buffer is full
// (64 KiB on Linux). Calling process.exit() immediately after main() returns
// makes the kernel drop the buffered tail, truncating output at the pipe
// boundary; `agent-style rules | less` loses the last ~25 KiB on Linux and
// macOS without this guard. Wait for both stdout and stderr to drain before
// exit by scheduling a zero-byte write whose callback only fires after the
// queued writes flush. EPIPE from a consumer that closed the pipe (e.g.
// `agent-style rules | head -3`) is swallowed as a clean exit.
function exitAfterDrain(code) {
  let pending = 2;
  const done = () => { if (--pending === 0) process.exit(code); };
  for (const s of [process.stdout, process.stderr]) {
    s.on('error', (err) => { if (err && err.code === 'EPIPE') process.exit(0); });
    s.write('', done);
  }
}
exitAfterDrain(exitCode);
