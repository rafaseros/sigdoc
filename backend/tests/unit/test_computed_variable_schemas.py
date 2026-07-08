"""Unit tests for the computed-variable pydantic schemas
(ComputedFormula / ComputedFunctionSpec) — the per-field / single-model
validations that pydantic can express without cross-variable context.

Cross-variable rules (source exists, is numeric, isn't itself computed) are
covered separately in tests/unit/test_template_service.py::TestUpdateVariableTypesComputed
since they require the full merged variables_meta.
"""

import pytest
from pydantic import ValidationError

from app.presentation.schemas.template import (
    ComputedFormula,
    ComputedFunctionSpec,
    VariableTypeOverride,
)


class TestComputedFormulaSchema:
    def test_valid_formula_accepted(self) -> None:
        spec = ComputedFormula(source="monto", operator="+", operand=100)
        assert spec.kind == "formula"
        assert spec.operator == "+"
        assert spec.operand == 100

    @pytest.mark.parametrize("operator", ["+", "-", "*", "/"])
    def test_all_four_operators_accepted(self, operator: str) -> None:
        operand = 2 if operator == "/" else 100
        spec = ComputedFormula(source="monto", operator=operator, operand=operand)
        assert spec.operator == operator

    def test_unknown_operator_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComputedFormula(source="monto", operator="%", operand=100)

    def test_division_by_zero_operand_rejected(self) -> None:
        with pytest.raises(ValidationError, match="0"):
            ComputedFormula(source="monto", operator="/", operand=0)

    def test_non_zero_division_operand_accepted(self) -> None:
        spec = ComputedFormula(source="monto", operator="/", operand=2)
        assert spec.operand == 2

    def test_infinite_operand_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComputedFormula(source="monto", operator="+", operand=float("inf"))

    def test_nan_operand_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComputedFormula(source="monto", operator="+", operand=float("nan"))

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComputedFormula(
                source="monto", operator="+", operand=1, unexpected="nope"
            )


class TestComputedFunctionSchema:
    def test_valid_function_accepted(self) -> None:
        spec = ComputedFunctionSpec(function="number_to_words", source="monto")
        assert spec.kind == "function"
        assert spec.function == "number_to_words"

    def test_unknown_function_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComputedFunctionSpec(function="not_a_real_function", source="monto")

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComputedFunctionSpec(
                function="number_to_words", source="monto", unexpected="nope"
            )


class TestVariableTypeOverrideComputedDiscriminator:
    def test_override_with_formula_computed(self) -> None:
        override = VariableTypeOverride(
            name="total",
            type="decimal",
            computed={"kind": "formula", "source": "monto", "operator": "+", "operand": 1},
        )
        assert isinstance(override.computed, ComputedFormula)

    def test_override_with_function_computed(self) -> None:
        override = VariableTypeOverride(
            name="total_en_letras",
            type="text",
            computed={"kind": "function", "function": "number_to_words", "source": "monto"},
        )
        assert isinstance(override.computed, ComputedFunctionSpec)

    def test_override_without_computed_defaults_to_none(self) -> None:
        override = VariableTypeOverride(name="monto", type="decimal")
        assert override.computed is None

    def test_unknown_discriminator_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VariableTypeOverride(
                name="total",
                type="decimal",
                computed={"kind": "unknown", "source": "monto"},
            )
