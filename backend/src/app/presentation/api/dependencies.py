"""Shared FastAPI dependencies for HTTP-layer permission gating.

These wrap the pure-domain helpers in `app.domain.services.permissions` and
translate a `False` answer into a 403 HTTPException with a uniform Spanish
error detail. Endpoints should pick the dependency that matches the
capability being gated (NOT a generic "is admin" check) so that future role
changes can target individual capabilities.

If you need a one-off capability gate that doesn't have a pre-bound
dependency, use `require_capability(check)`.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.domain.services.permissions import (
    can_manage_own_templates,
    can_manage_users,
    can_view_audit,
    can_view_tenant_usage,
)
from app.presentation.middleware.tenant import CurrentUser, get_current_user

_FORBIDDEN_DETAIL = "Solo administradores pueden realizar esta acción"


def require_capability(
    check: Callable[[str], bool],
) -> Callable[[CurrentUser], CurrentUser]:
    """Build a FastAPI dependency that gates a route on a permission helper.

    Usage::

        @router.get("/foo", dependencies=[Depends(require_capability(can_view_audit))])
        async def list_foo(...): ...

    Or, when the route also needs the `CurrentUser`::

        async def list_foo(
            current_user: CurrentUser = Depends(require_capability(can_view_audit)),
        ): ...
    """

    def _dep(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not check(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_FORBIDDEN_DETAIL,
            )
        return current_user

    return _dep


# Pre-bound dependencies for the common capabilities. Use these in routes for
# clarity and to avoid recreating the closure on every request graph.
require_user_manager = require_capability(can_manage_users)
require_audit_viewer = require_capability(can_view_audit)
require_tenant_usage_viewer = require_capability(can_view_tenant_usage)
require_template_manager = require_capability(can_manage_own_templates)
