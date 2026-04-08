# Rate Limiting Specification

## Purpose

Define requirements for protecting sensitive and resource-intensive endpoints against brute-force and abuse using per-IP rate limits via `slowapi`.

## Requirements

### Requirement: Rate Limiter Dependency and Setup

`slowapi>=0.1.9` MUST be added to the production dependencies in `pyproject.toml`.

A rate limiter instance MUST be configured in `main.py` (or a dedicated middleware module) using the client IP (`request.client.host`) as the rate limit key.

The `SlowAPIMiddleware` (or equivalent Starlette exception handler for `RateLimitExceeded`) MUST be registered with the FastAPI app so that limit violations return HTTP 429.

#### Scenario: Rate limiter middleware is registered

- GIVEN the FastAPI app is started
- WHEN `GET /openapi.json` is inspected for middleware
- THEN the slowapi middleware or exception handler is present in the app's middleware stack

---

### Requirement: Auth Endpoint Rate Limits

`POST /auth/login` MUST be limited to **5 requests per minute** per client IP.

`POST /auth/refresh` MUST be limited to **10 requests per minute** per client IP.

#### Scenario: Login blocked after 5 attempts per minute

- GIVEN a client IP makes 5 successful or failed `POST /auth/login` requests within 60 seconds
- WHEN the same client IP makes a 6th request within the same window
- THEN the response is HTTP 429
- AND the response body contains a rate limit error message

#### Scenario: Login allowed within limit

- GIVEN a client IP has made fewer than 5 `POST /auth/login` requests in the current window
- WHEN another request is made
- THEN the response is NOT HTTP 429

#### Scenario: Refresh blocked after 10 attempts per minute

- GIVEN a client IP makes 10 `POST /auth/refresh` requests within 60 seconds
- WHEN the same IP makes an 11th request
- THEN the response is HTTP 429

---

### Requirement: Document Generation Endpoint Rate Limits

`POST /documents/generate` MUST be limited to **20 requests per minute** per client IP.

`POST /documents/generate-bulk` MUST be limited to **5 requests per minute** per client IP.

#### Scenario: Single generation blocked after 20 requests per minute

- GIVEN a client IP makes 20 `POST /documents/generate` requests within 60 seconds
- WHEN the same IP makes a 21st request
- THEN the response is HTTP 429

#### Scenario: Bulk generation blocked after 5 requests per minute

- GIVEN a client IP makes 5 `POST /documents/generate-bulk` requests within 60 seconds
- WHEN the same IP makes a 6th request
- THEN the response is HTTP 429

#### Scenario: Different IPs have independent counters

- GIVEN client IP A has exhausted its `POST /auth/login` limit (5/min)
- WHEN client IP B makes its first `POST /auth/login` request
- THEN the response is NOT HTTP 429

---

### Requirement: Rate Limit Configuration via Settings

Rate limit values SHOULD be configurable via `Settings` (e.g. `rate_limit_login`, `rate_limit_generation`) with documented defaults.

#### Scenario: Default limits applied when env vars are absent

- GIVEN no rate-limit env vars are set
- WHEN the app starts
- THEN the limiter uses the defaults: login=5/min, refresh=10/min, generate=20/min, bulk=5/min
