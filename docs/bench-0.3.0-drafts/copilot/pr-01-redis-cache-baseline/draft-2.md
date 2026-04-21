This change moves the session cache from the in-process LRU to Redis so session state is shared across instances, survives app restarts, and scales more predictably under horizontal load.  
The rollout plan is to deploy Redis-backed caching behind a feature flag, enable it for a small canary slice first, monitor latency/error rates and cache hit behavior, then ramp to 100% and remove the old LRU path after stability is confirmed.  
The biggest trade-off is that session reads and writes now depend on an external network service, which adds operational complexity and can increase tail latency compared with in-memory access.  
In return, we eliminate per-instance cache divergence and unlock consistent session behavior across the fleet.

