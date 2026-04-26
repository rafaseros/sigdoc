# Capability: pdf-conversion

## Purpose

This capability introduces the `PdfConverter` domain port and its Gotenberg-backed adapter. It defines the contract for converting DOCX bytes to PDF bytes, the failure semantics (domain exception hierarchy), configuration surface, infrastructure dependency (Gotenberg sidecar), test double, and observability requirements. All other capabilities that require DOCX→PDF conversion depend on this one.

## Requirements

### REQ-PDF-01: PdfConverter port interface

The `PdfConverter` port MUST define an abstract async method `convert(docx_bytes: bytes) -> bytes`. Implementations MUST raise `PdfConversionError` on any failure and MUST NOT raise any other exception type for conversion failures. Empty `docx_bytes` MUST be treated as an invalid input and raise `PdfConversionError`.

### REQ-PDF-02: GotenbergPdfConverter adapter

The `GotenbergPdfConverter` adapter MUST implement `PdfConverter` using `httpx.AsyncClient`. It MUST POST the DOCX bytes as a multipart file field to `{GOTENBERG_URL}/forms/libreoffice/convert` and return the raw response body as PDF bytes on HTTP 2xx.

### REQ-PDF-03: Configurable Gotenberg settings

`backend/src/app/config.py` MUST expose `gotenberg_url: str` (default `"http://gotenberg:3000"`) and `gotenberg_timeout: int` (default `60`, unit: seconds). The adapter MUST read both values from `Settings`.

### REQ-PDF-04: httpx production dependency

`httpx` MUST appear in `[project.dependencies]` in `backend/pyproject.toml`, pinned `>=0.27.0,<1.0`. It MUST NOT remain only under `[project.optional-dependencies]`.

### REQ-PDF-05: Gotenberg service in docker-compose

`docker/docker-compose.yml` MUST include a `gotenberg` service using image `gotenberg/gotenberg:8`, internal port 3000, a healthcheck against `http://localhost:3000/health`, connected to the `sigdoc` network. The `api` service MUST declare `depends_on: gotenberg: condition: service_healthy`.

### REQ-PDF-06: PdfConversionError is a domain exception

`PdfConversionError` MUST extend `DomainError` (the base class in `backend/src/app/domain/exceptions.py`) and MUST accept a descriptive `message: str` in its constructor. It MUST NOT be defined in the infrastructure layer.

### REQ-PDF-07: FakePdfConverter test double

`backend/tests/fakes/fake_pdf_converter.py` MUST provide a `FakePdfConverter` that implements `PdfConverter`. It MUST support controllable modes: a configurable `convert_result: bytes` returned on success, and a `set_failure(exc: PdfConversionError)` method that causes the next `convert()` call to raise the configured exception. After raising, the failure state MUST be cleared (single-use).

### REQ-PDF-08: HTTP error translation

`GotenbergPdfConverter` MUST translate all of the following into `PdfConversionError` with a descriptive message:
- Gotenberg HTTP 4xx responses
- Gotenberg HTTP 5xx responses
- `httpx.TimeoutException` (any subclass)
- `httpx.ConnectError` and other `httpx.RequestError` subclasses

No HTTP error or network error from `httpx` MUST propagate to the caller as a raw `httpx` exception.

### REQ-PDF-09: Conversion observability

`GotenbergPdfConverter` MUST log conversion duration (in milliseconds) and outcome on every call using the existing application logger. On success: log level INFO with duration. On failure: log level ERROR with failure type and duration.

### REQ-PDF-10: Non-blocking async execution

`GotenbergPdfConverter` MUST use `httpx.AsyncClient` (not `httpx.Client`). The `convert` method MUST be declared `async`. It MUST NOT call `asyncio.to_thread` to wrap a sync HTTP call; the call MUST be natively async.

## Scenarios

### SCEN-PDF-01: Happy path — valid DOCX bytes converted to PDF
**Given**: A `GotenbergPdfConverter` configured with a reachable Gotenberg instance
**When**: `convert(docx_bytes)` is called with non-empty valid DOCX bytes
**Then**: The method returns `bytes` whose length > 0 and whose content is a valid PDF
**And**: An INFO log entry records the conversion duration in milliseconds

### SCEN-PDF-02: Gotenberg returns HTTP 5xx
**Given**: Gotenberg responds with a 500 status code
**When**: `convert(docx_bytes)` is called
**Then**: `PdfConversionError` is raised with a message referencing the HTTP status code
**And**: No `httpx` exception propagates to the caller

### SCEN-PDF-03: Gotenberg connection refused
**Given**: No Gotenberg instance is listening at `GOTENBERG_URL`
**When**: `convert(docx_bytes)` is called
**Then**: `PdfConversionError` is raised with a message indicating connection failure
**And**: An ERROR log entry is written

### SCEN-PDF-04: Gotenberg times out
**Given**: Gotenberg does not respond within `GOTENBERG_TIMEOUT` seconds
**When**: `convert(docx_bytes)` is called
**Then**: `PdfConversionError` is raised with a message explicitly referencing timeout
**And**: An ERROR log entry records the timeout event and elapsed duration

### SCEN-PDF-05: Empty input bytes
**Given**: A `GotenbergPdfConverter` configured normally
**When**: `convert(b"")` is called with zero-length bytes
**Then**: `PdfConversionError` is raised before any HTTP request is made
**And**: The error message indicates that empty input is invalid

### SCEN-PDF-06: FakePdfConverter failure injection
**Given**: A `FakePdfConverter` instance with `set_failure(PdfConversionError("forced"))` called
**When**: `convert(docx_bytes)` is called
**Then**: `PdfConversionError("forced")` is raised
**And**: A subsequent call to `convert(docx_bytes)` (with `convert_result` set) succeeds normally, confirming the failure state was cleared
