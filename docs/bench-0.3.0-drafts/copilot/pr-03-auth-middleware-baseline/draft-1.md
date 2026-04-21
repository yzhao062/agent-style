This PR removes the legacy cookie-based auth middleware and makes header-based JWT bearer authentication the only supported scheme across the stack.  
All callers that still rely on auth cookies must migrate to sending `Authorization: Bearer <token>` headers by **2026-06-30**.  
As part of the rollout, the deprecation messaging is updated to clearly state that cookie-based auth is retired, unsupported, and scheduled for removal by that deadline.  
Any remaining integrations using cookies should treat current warnings as final notice and update their clients before the cutoff to avoid authentication failures.  
This change simplifies the auth path, eliminates dual-scheme ambiguity, and aligns all consumers on a single JWT-based contract.

