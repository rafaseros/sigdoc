from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tenant_id: str
    effective_bulk_limit: int | None = None
    # Per single-org-cutover (REQ-SOS-14): always True; column kept for Nivel B.
    email_verified: bool = True

    model_config = {"from_attributes": True}


# REMOVED per single-org-cutover (REQ-SOS-01 / T-3-06):
# - SignupRequest, SignupResponse, SignupUserResponse (signup route disabled)
# - ForgotPasswordRequest, ResetPasswordRequest (self-service password reset disabled)
# These will be deleted in Nivel B alongside the service files.
