The auth service handles login requests. The auth service also validates tokens. The auth service rate-limits per user.

We need three things done:

- Login
- Logout

The migration path has four phases. The migration path starts with dual-write. The migration path ends with read-path cutover.

In conclusion, these updates represent a significant step forward for our authentication story.
