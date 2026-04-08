"""Unit tests for domain exceptions (task 3.1)."""
import pytest

from app.domain.exceptions import (
    BulkLimitExceededError,
    DocumentNotFoundError,
    DomainError,
    InvalidTemplateError,
    TemplateNotFoundError,
    TemplateVersionNotFoundError,
    VariablesMismatchError,
)


class TestBulkLimitExceededError:
    def test_carries_limit_value(self):
        err = BulkLimitExceededError(limit=25)
        assert err.limit == 25

    def test_str_contains_limit(self):
        err = BulkLimitExceededError(limit=25)
        assert "25" in str(err)

    def test_default_limit_is_10(self):
        err = BulkLimitExceededError()
        assert err.limit == 10
        assert "10" in str(err)

    def test_is_domain_error(self):
        err = BulkLimitExceededError(limit=5)
        assert isinstance(err, DomainError)

    def test_is_exception(self):
        err = BulkLimitExceededError(limit=5)
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(BulkLimitExceededError) as exc_info:
            raise BulkLimitExceededError(limit=100)
        assert exc_info.value.limit == 100

    def test_can_be_caught_as_domain_error(self):
        with pytest.raises(DomainError):
            raise BulkLimitExceededError(limit=5)


class TestVariablesMismatchError:
    def test_is_domain_error(self):
        err = VariablesMismatchError("mismatch")
        assert isinstance(err, DomainError)

    def test_can_be_raised(self):
        with pytest.raises(VariablesMismatchError):
            raise VariablesMismatchError("missing: foo, extra: bar")

    def test_str_message(self):
        err = VariablesMismatchError("missing: foo")
        assert "missing: foo" in str(err)


class TestOtherDomainExceptions:
    @pytest.mark.parametrize(
        "exc_class",
        [
            TemplateNotFoundError,
            TemplateVersionNotFoundError,
            DocumentNotFoundError,
            InvalidTemplateError,
        ],
    )
    def test_is_domain_error_subclass(self, exc_class):
        err = exc_class("test message")
        assert isinstance(err, DomainError)
        assert isinstance(err, Exception)

    @pytest.mark.parametrize(
        "exc_class",
        [
            TemplateNotFoundError,
            TemplateVersionNotFoundError,
            DocumentNotFoundError,
            InvalidTemplateError,
            VariablesMismatchError,
        ],
    )
    def test_can_be_caught_as_domain_error(self, exc_class):
        with pytest.raises(DomainError):
            raise exc_class("test")
