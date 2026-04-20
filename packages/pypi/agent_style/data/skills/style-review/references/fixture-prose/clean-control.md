Switch session caching from in-memory LRU to Redis with a 5-minute TTL.

Sessions now survive pod restarts; per-pod memory drops from 1.2 GB to 280 MB.

Trade-off: a Redis outage logs all users out. Session lookup already fails closed, so the user impact is a 401 rather than a 500.

Rollout plan: deploy the Redis client as a dual-write shadow for one week, then flip read-path in region us-east-1 first. Monitor session-creation P99 latency.
