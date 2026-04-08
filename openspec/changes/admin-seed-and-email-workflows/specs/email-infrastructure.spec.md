# Spec: Email Infrastructure

**Change**: `admin-seed-and-email-workflows`
**Module**: `email-infrastructure`
**Status**: specified

## Requirements

### REQ-EMAIL-01: EmailService Port

A new domain port `EmailService` SHALL define the contract for sending emails:

```python
class EmailService(ABC):
    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        """Send an email. Returns True if accepted for delivery, False on failure."""
        ...
```

The port lives at `app/domain/ports/email_service.py`.

### REQ-EMAIL-02: SMTP Adapter

An SMTP adapter SHALL implement `EmailService` using `aiosmtplib`:

- Connects to the configured SMTP server
- Sends multipart emails (HTML + optional plain text)
- Returns `True` on success, `False` on any SMTP error (never raises)
- Logs errors via Python logging (does NOT propagate exceptions to caller)

### REQ-EMAIL-03: Console Adapter (Dev/Test)

A console adapter SHALL implement `EmailService` by logging email details to stdout:

- Logs: recipient, subject, and body (truncated to 500 chars)
- Always returns `True`
- Stores sent emails in an in-memory list for test assertions

### REQ-EMAIL-04: Email Configuration

New fields in `Settings`:

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `smtp_host` | `str` | `""` | No |
| `smtp_port` | `int` | `587` | No |
| `smtp_user` | `str` | `""` | No |
| `smtp_password` | `str` | `""` | No |
| `smtp_from_address` | `str` | `"noreply@sigdoc.local"` | No |
| `smtp_tls` | `bool` | `True` | No |
| `email_backend` | `str` | `"console"` | No |

When `email_backend` is `"smtp"`, the SMTP adapter is used. When `"console"`, the console adapter is used. Default is `"console"` so dev environments work out of the box.

### REQ-EMAIL-05: Email Templates

HTML email templates SHALL be stored at `backend/src/app/infrastructure/email/templates/`:

- `verification.html` — email verification template
- `password_reset.html` — password reset template

Templates use Jinja2 with variables:
- `{{ app_name }}` — "SigDoc"
- `{{ user_name }}` — recipient's full name
- `{{ action_url }}` — the verification/reset link
- `{{ expires_in }}` — human-readable expiry ("24 hours" / "1 hour")

### REQ-EMAIL-06: EmailService Dependency

A factory function `get_email_service()` SHALL return the appropriate adapter based on `Settings.email_backend`. It SHALL be usable as a FastAPI dependency.

## Scenarios

### SCEN-EMAIL-01: Send email via SMTP adapter
**Given** `email_backend` is `"smtp"` and SMTP is configured correctly
**When** `send_email(to="user@example.com", subject="Test", html_body="<p>Hi</p>")` is called
**Then** the email is sent via SMTP
**And** the method returns `True`

### SCEN-EMAIL-02: SMTP failure is handled gracefully
**Given** `email_backend` is `"smtp"` and SMTP server is unreachable
**When** `send_email(...)` is called
**Then** the method returns `False`
**And** the error is logged
**And** no exception propagates to the caller

### SCEN-EMAIL-03: Console adapter logs email
**Given** `email_backend` is `"console"`
**When** `send_email(to="user@example.com", subject="Test", html_body="<p>Hi</p>")` is called
**Then** the email details are printed to stdout
**And** the email is stored in the adapter's `sent_emails` list
**And** the method returns `True`

### SCEN-EMAIL-04: Default config uses console adapter
**Given** no `EMAIL_BACKEND` env var is set
**When** the application starts
**Then** `get_email_service()` returns a `ConsoleEmailService`
