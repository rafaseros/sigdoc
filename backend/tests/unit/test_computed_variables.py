"""Unit tests for the computed-variables pure domain module.

Covers:
- number_to_words(): exhaustive Spanish contract-style converter (no accents,
  "UN MIL" convention for 1000-1999, apocope of "UNO" before MIL/MILLON).
- resolve_computed(): formula ops, rounding, overwrite-user-value, empty
  source, div-by-constant behavior.
- computed_variable_names(): helper used to exclude computed vars from
  fillable/required counts.
"""

from decimal import Decimal

import pytest

from app.domain.exceptions import ComputedVariableError
from app.domain.services.computed_variables import (
    computed_variable_names,
    number_to_words,
    resolve_computed,
)


# ---------------------------------------------------------------------------
# number_to_words — exhaustive converter tests
# ---------------------------------------------------------------------------


class TestNumberToWordsContractExamples:
    """Exact examples mandated by the product contract."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("1500.50", "UN MIL QUINIENTOS 50/100"),
            ("1000", "UN MIL 00/100"),
            ("0.75", "CERO 75/100"),
            ("21", "VEINTIUNO 00/100"),
            ("100", "CIEN 00/100"),
            ("101", "CIENTO UNO 00/100"),
            ("16", "DIECISEIS 00/100"),
            ("1000000", "UN MILLON 00/100"),
            ("2000000", "DOS MILLONES 00/100"),
            ("500", "QUINIENTOS 00/100"),
            (
                "777777",
                "SETECIENTOS SETENTA Y SIETE MIL SETECIENTOS SETENTA Y SIETE 00/100",
            ),
        ],
    )
    def test_contract_examples(self, value: str, expected: str) -> None:
        assert number_to_words(Decimal(value)) == expected


class TestNumberToWordsBoundaries:
    """Boundary transitions called out explicitly by the spec."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("15", "QUINCE 00/100"),
            ("16", "DIECISEIS 00/100"),
            ("20", "VEINTE 00/100"),
            ("21", "VEINTIUNO 00/100"),
            ("29", "VEINTINUEVE 00/100"),
            ("30", "TREINTA 00/100"),
            ("100", "CIEN 00/100"),
            ("101", "CIENTO UNO 00/100"),
            ("199", "CIENTO NOVENTA Y NUEVE 00/100"),
            ("200", "DOSCIENTOS 00/100"),
            ("201", "DOSCIENTOS UNO 00/100"),
            ("999", "NOVECIENTOS NOVENTA Y NUEVE 00/100"),
            ("1000", "UN MIL 00/100"),
            ("21000", "VEINTIUN MIL 00/100"),
            ("100000", "CIEN MIL 00/100"),
            ("1000000", "UN MILLON 00/100"),
        ],
    )
    def test_boundaries(self, value: str, expected: str) -> None:
        assert number_to_words(Decimal(value)) == expected


class TestNumberToWordsCents:
    @pytest.mark.parametrize(
        "value,expected_suffix",
        [
            ("10.00", "00/100"),
            ("10.05", "05/100"),
            ("10.99", "99/100"),
        ],
    )
    def test_cents_formatting(self, value: str, expected_suffix: str) -> None:
        assert number_to_words(Decimal(value)).endswith(expected_suffix)

    def test_rounding_of_more_than_two_decimals_half_up(self) -> None:
        # 21.005 -> ROUND_HALF_UP -> 21.01
        assert number_to_words(Decimal("21.005")) == "VEINTIUNO 01/100"

    def test_rounding_down_when_third_decimal_below_half(self) -> None:
        # 21.004 -> ROUND_HALF_UP -> 21.00
        assert number_to_words(Decimal("21.004")) == "VEINTIUNO 00/100"


class TestNumberToWordsErrors:
    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            number_to_words(Decimal("-1"))

    def test_beyond_max_raises(self) -> None:
        with pytest.raises(ValueError):
            number_to_words(Decimal("1000000000"))

    def test_max_boundary_is_allowed(self) -> None:
        # 999,999,999.99 is the documented maximum — must NOT raise.
        result = number_to_words(Decimal("999999999.99"))
        assert result.endswith("99/100")


# ---------------------------------------------------------------------------
# resolve_computed — formula + function resolution
# ---------------------------------------------------------------------------


def _meta_formula(name: str, source: str, operator: str, operand: float, source_type: str = "decimal") -> list[dict]:
    return [
        {"name": source, "type": source_type, "contexts": []},
        {
            "name": name,
            "type": "decimal",
            "contexts": [],
            "computed": {
                "kind": "formula",
                "source": source,
                "operator": operator,
                "operand": operand,
            },
        },
    ]


def _meta_function(name: str, source: str, function: str, source_type: str = "decimal") -> list[dict]:
    return [
        {"name": source, "type": source_type, "contexts": []},
        {
            "name": name,
            "type": "text",
            "contexts": [],
            "computed": {"kind": "function", "function": function, "source": source},
        },
    ]


class TestResolveComputedFormula:
    def test_addition(self) -> None:
        meta = _meta_formula("total_con_iva", "monto", "+", 100)
        result = resolve_computed(meta, {"monto": "400.00"})
        assert result["total_con_iva"] == "500.00"

    def test_subtraction(self) -> None:
        meta = _meta_formula("neto", "bruto", "-", 50)
        result = resolve_computed(meta, {"bruto": "200"})
        assert result["neto"] == "150.00"

    def test_multiplication(self) -> None:
        meta = _meta_formula("doble", "monto", "*", 2)
        result = resolve_computed(meta, {"monto": "21"})
        assert result["doble"] == "42.00"

    def test_division(self) -> None:
        meta = _meta_formula("mitad", "monto", "/", 2)
        result = resolve_computed(meta, {"monto": "9"})
        assert result["mitad"] == "4.50"

    def test_quantizes_to_two_decimals_round_half_up(self) -> None:
        meta = _meta_formula("tercio", "monto", "/", 3)
        result = resolve_computed(meta, {"monto": "10"})
        # 10/3 = 3.3333... -> ROUND_HALF_UP to 2 decimals = 3.33
        assert result["tercio"] == "3.33"

    def test_zero_operand_division_raises_computed_variable_error(self) -> None:
        """Defense-in-depth (W-COMP-05): save-time validation already
        rejects operand=0 for '/', but legacy/out-of-band variables_meta
        (e.g. injected directly, bypassing the pydantic schema) must not
        crash the process with an uncaught ZeroDivisionError."""
        meta = _meta_formula("mitad", "monto", "/", 0)
        with pytest.raises(ComputedVariableError):
            resolve_computed(meta, {"monto": "9"})

    def test_unknown_operator_raises_computed_variable_error(self) -> None:
        """Defense-in-depth: save-time validation constrains operator to the
        supported set, but legacy/out-of-band variables_meta could carry an
        unknown operator. It must raise ComputedVariableError (→ 422), not a
        bare KeyError (→ 500), like the guarded division path."""
        meta = _meta_formula("weird", "monto", "%", 2)
        with pytest.raises(ComputedVariableError):
            resolve_computed(meta, {"monto": "10"})

    def test_overwrites_user_supplied_value_for_computed_name(self) -> None:
        """Server-authoritative: any user-supplied value for a computed name
        must be overwritten by the resolved value."""
        meta = _meta_formula("total_con_iva", "monto", "+", 100)
        result = resolve_computed(
            meta, {"monto": "400.00", "total_con_iva": "999999.99"}
        )
        assert result["total_con_iva"] == "500.00"

    def test_missing_source_computes_to_empty_string(self) -> None:
        meta = _meta_formula("total_con_iva", "monto", "+", 100)
        result = resolve_computed(meta, {})
        assert result["total_con_iva"] == ""

    def test_unparseable_source_computes_to_empty_string(self) -> None:
        meta = _meta_formula("total_con_iva", "monto", "+", 100)
        result = resolve_computed(meta, {"monto": "not-a-number"})
        assert result["total_con_iva"] == ""

    def test_does_not_mutate_non_computed_values(self) -> None:
        meta = _meta_formula("total_con_iva", "monto", "+", 100)
        result = resolve_computed(meta, {"monto": "1", "other": "unchanged"})
        assert result["other"] == "unchanged"
        assert result["monto"] == "1"


class TestResolveComputedFunction:
    def test_number_to_words_wired_through(self) -> None:
        meta = _meta_function("monto_en_letras", "monto", "number_to_words")
        result = resolve_computed(meta, {"monto": "1500.50"})
        assert result["monto_en_letras"] == "UN MIL QUINIENTOS 50/100"

    def test_missing_source_computes_to_empty_string(self) -> None:
        meta = _meta_function("monto_en_letras", "monto", "number_to_words")
        result = resolve_computed(meta, {})
        assert result["monto_en_letras"] == ""

    def test_unparseable_source_computes_to_empty_string(self) -> None:
        meta = _meta_function("monto_en_letras", "monto", "number_to_words")
        result = resolve_computed(meta, {"monto": "abc"})
        assert result["monto_en_letras"] == ""

    def test_negative_source_raises_computed_variable_error(self) -> None:
        meta = _meta_function("monto_en_letras", "monto", "number_to_words")
        with pytest.raises(ComputedVariableError):
            resolve_computed(meta, {"monto": "-5"})

    def test_out_of_range_source_raises_computed_variable_error(self) -> None:
        meta = _meta_function("monto_en_letras", "monto", "number_to_words")
        with pytest.raises(ComputedVariableError):
            resolve_computed(meta, {"monto": "1000000000"})


class TestResolveComputedMultipleEntries:
    def test_multiple_computed_variables_resolved_independently(self) -> None:
        meta = [
            {"name": "monto", "type": "decimal", "contexts": []},
            {
                "name": "total_con_iva",
                "type": "decimal",
                "contexts": [],
                "computed": {
                    "kind": "formula",
                    "source": "monto",
                    "operator": "+",
                    "operand": 100,
                },
            },
            {
                "name": "monto_en_letras",
                "type": "text",
                "contexts": [],
                "computed": {
                    "kind": "function",
                    "function": "number_to_words",
                    "source": "monto",
                },
            },
        ]
        result = resolve_computed(meta, {"monto": "900"})
        assert result["total_con_iva"] == "1000.00"
        assert result["monto_en_letras"] == "NOVECIENTOS 00/100"

    def test_entries_without_computed_are_ignored(self) -> None:
        meta = [{"name": "plain", "type": "text", "contexts": []}]
        result = resolve_computed(meta, {"plain": "hello"})
        assert result == {"plain": "hello"}

    def test_empty_meta_returns_copy_of_user_values(self) -> None:
        values = {"a": "1"}
        result = resolve_computed([], values)
        assert result == values
        assert result is not values


class TestComputedVariableNames:
    def test_returns_names_with_computed_spec(self) -> None:
        meta = _meta_formula("total_con_iva", "monto", "+", 100)
        assert computed_variable_names(meta) == {"total_con_iva"}

    def test_returns_empty_set_when_none_computed(self) -> None:
        meta = [{"name": "plain", "type": "text", "contexts": []}]
        assert computed_variable_names(meta) == set()

    def test_handles_empty_or_none_meta(self) -> None:
        assert computed_variable_names([]) == set()
        assert computed_variable_names(None) == set()
