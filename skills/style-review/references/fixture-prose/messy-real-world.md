---
title: Session cache migration
author: platform-team
date: 2026-05-01
---

# Session Cache Migration Plan

## Current State

The session cache lives in-memory per pod. This works well for low traffic but has two operational problems:

| Problem | Impact | Frequency |
| --- | --- | --- |
| Pod restart invalidates sessions | user re-login | ~3x / day |
| Memory per pod grows with active sessions | OOM at scale | weekly |

## Proposed Change

Switch to Redis with a 5-minute TTL. The new client wraps `redis.py` with a circuit breaker.

```python
from redis import Redis
client = Redis(host="redis-prod", socket_timeout=1.0)
session = client.get(f"session:{token}")  # leverages connection pooling
```

Note: the `leverages` in the code comment above is intentional and should NOT be flagged by the detectors — it is inside a fenced code block.

## Rollout

Deploy in three stages. Stage one is a dual-write shadow. Stage two flips reads in us-east-1. Stage three flips reads globally.

Risk: a Redis outage logs all users out. Mitigation: session lookup fails closed to 401, not 500.
