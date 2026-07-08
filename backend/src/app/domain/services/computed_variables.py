"""Domain service: computed-variable resolution and validation.

Computed variables let a template author derive a variable's value from
another ("source") variable at generation/preview time instead of asking the
end user to type it in — e.g. a total-with-surcharge formula, or a Spanish
"amount in words" rendering for a legal contract.

Two kinds are supported (v1, no chaining):
    - "formula":  Decimal(source) <operator> Decimal(operand), quantized to
      2 decimals (ROUND_HALF_UP), rendered as a plain "450.00" string.
    - "function": a named pure conversion applied to the source value. Only
      "number_to_words" exists today (registry pattern — see
      `_FUNCTION_REGISTRY` — designed so a new function is a one-line add).

This module is pure: no I/O, no persistence, no framework imports. It is the
SINGLE source of truth for computed-variable resolution — both
`DocumentService.generate_single` and `DocumentService.preview` call
`resolve_computed()` so the two code paths can never drift.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.domain.exceptions import ComputedVariableError

# ---------------------------------------------------------------------------
# number_to_words — Spanish contract-style converter (no accents, uppercase)
# ---------------------------------------------------------------------------

# Contract convention: uppercase, NO accents (e.g. "DIECISEIS" not
# "DIECISÉIS", "VEINTIDOS" not "VEINTIDÓS") — this matches existing legal
# document contract conventions and must not be "corrected" to add accents.
_ONES = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]

_TEENS = {
    10: "DIEZ",
    11: "ONCE",
    12: "DOCE",
    13: "TRECE",
    14: "CATORCE",
    15: "QUINCE",
    16: "DIECISEIS",
    17: "DIECISIETE",
    18: "DIECIOCHO",
    19: "DIECINUEVE",
}

_TWENTIES = {
    20: "VEINTE",
    21: "VEINTIUNO",
    22: "VEINTIDOS",
    23: "VEINTITRES",
    24: "VEINTICUATRO",
    25: "VEINTICINCO",
    26: "VEINTISEIS",
    27: "VEINTISIETE",
    28: "VEINTIOCHO",
    29: "VEINTINUEVE",
}

_TENS = {
    30: "TREINTA",
    40: "CUARENTA",
    50: "CINCUENTA",
    60: "SESENTA",
    70: "SETENTA",
    80: "OCHENTA",
    90: "NOVENTA",
}

_HUNDRED_PREFIXES = {
    1: "CIENTO",
    2: "DOSCIENTOS",
    3: "TRESCIENTOS",
    4: "CUATROCIENTOS",
    5: "QUINIENTOS",
    6: "SEISCIENTOS",
    7: "SETECIENTOS",
    8: "OCHOCIENTOS",
    9: "NOVECIENTOS",
}

_MAX_NUMBER_TO_WORDS = Decimal("999999999.99")


def _tens_and_units_to_words(n: int) -> str:
    """Convert 0-99 to words. Returns '' for 0."""
    if n == 0:
        return ""
    if n < 10:
        return _ONES[n]
    if n in _TEENS:
        return _TEENS[n]
    if n in _TWENTIES:
        return _TWENTIES[n]
    tens_digit = (n // 10) * 10
    unit = n % 10
    if unit == 0:
        return _TENS[tens_digit]
    return f"{_TENS[tens_digit]} Y {_ONES[unit]}"


def _group_to_words(n: int) -> str:
    """Convert 0-999 to words. Returns '' for 0."""
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    hundreds_digit = n // 100
    remainder = n % 100
    parts: list[str] = []
    if hundreds_digit:
        parts.append(_HUNDRED_PREFIXES[hundreds_digit])
    rest = _tens_and_units_to_words(remainder)
    if rest:
        parts.append(rest)
    return " ".join(parts)


def _apocope_before_scale(words: str) -> str:
    """Apply the Spanish apocope rule: a trailing 'UNO' becomes 'UN' when the
    group is immediately followed by a scale word (MIL / MILLON[ES]).

    Handles all forms uniformly since it only checks the string's ending:
    "UNO" -> "UN", "VEINTIUNO" -> "VEINTIUN", "CIENTO UNO" -> "CIENTO UN",
    "TREINTA Y UNO" -> "TREINTA Y UN".
    """
    if words.endswith("UNO"):
        return words[:-1]
    return words


def _integer_to_words(n: int) -> str:
    """Convert a non-negative integer (0 to 999,999,999) to Spanish words."""
    if n == 0:
        return "CERO"

    millions, remainder = divmod(n, 1_000_000)
    thousands, rest = divmod(remainder, 1000)

    parts: list[str] = []

    if millions:
        millions_words = _apocope_before_scale(_group_to_words(millions))
        if millions == 1:
            parts.append(f"{millions_words} MILLON")
        else:
            parts.append(f"{millions_words} MILLONES")

    if thousands:
        thousands_words = _apocope_before_scale(_group_to_words(thousands))
        parts.append(f"{thousands_words} MIL")

    if rest:
        parts.append(_group_to_words(rest))

    return " ".join(parts)


def number_to_words(value: Decimal) -> str:
    """Convert a monetary Decimal amount to Spanish contract-style words.

    Format: "<INTEGER PART IN WORDS> NN/100" — no currency name, uppercase,
    no accents. Supports 0 up to 999,999,999.99 inclusive.

    Raises:
        ValueError: value is negative, or exceeds the supported maximum.
    """
    if value < 0:
        raise ValueError("No se puede convertir un número negativo a palabras")
    if value > _MAX_NUMBER_TO_WORDS:
        raise ValueError(
            "El número supera el máximo soportado (999.999.999,99) para "
            "conversión a palabras"
        )

    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    scaled = int(quantized * 100)
    integer_part, cents = divmod(scaled, 100)

    words = _integer_to_words(integer_part)
    return f"{words} {cents:02d}/100"


# ---------------------------------------------------------------------------
# resolve_computed — server-authoritative computed-variable resolution
# ---------------------------------------------------------------------------

_OPERATORS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
}


def _get(entry, key, default=None):
    """Read `key` from `entry`, whether it's a dict or an object with attrs."""
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _parse_decimal(raw: str | None) -> Decimal | None:
    """Parse a string into Decimal. Returns None on missing/blank/unparseable
    input — callers use this to implement the "compute to empty string"
    safety net for partial (in-progress) fills."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _compute_formula(source_value: str | None, operator: str, operand: float) -> str:
    source_decimal = _parse_decimal(source_value)
    if source_decimal is None:
        return ""

    op = _OPERATORS[operator]
    # Defense-in-depth: save-time validation already rejects operand=0 for
    # "/" (see ComputedFormula schema), but legacy or out-of-band
    # variables_meta could still reach here with a zero operand — guard the
    # division itself instead of trusting upstream validation exclusively.
    # Decimal division by zero raises decimal.DivisionByZero (a
    # ZeroDivisionError subclass) for a nonzero numerator, and
    # decimal.InvalidOperation for 0/0.
    try:
        result = op(source_decimal, Decimal(str(operand)))
    except (ZeroDivisionError, InvalidOperation) as exc:
        raise ComputedVariableError(
            "No se puede dividir por cero en una variable calculada."
        ) from exc
    quantized = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(quantized)


# Registry pattern (per product decision) — adding a new function is a
# one-line addition here, plus a Literal update in the presentation schema.
_FUNCTION_REGISTRY = {
    "number_to_words": number_to_words,
}


def _compute_function(function: str, source_value: str | None) -> str:
    source_decimal = _parse_decimal(source_value)
    if source_decimal is None:
        return ""

    func = _FUNCTION_REGISTRY.get(function)
    if func is None:
        raise ComputedVariableError(f"Función calculada desconocida: '{function}'")

    try:
        return func(source_decimal)
    except ValueError as exc:
        raise ComputedVariableError(str(exc)) from exc


def resolve_computed(
    variables_meta: list[dict] | None, user_values: dict[str, str]
) -> dict[str, str]:
    """Return the FULL variables dict with computed values resolved.

    Starts from a shallow copy of `user_values` and overwrites (or adds) the
    key for every variable in `variables_meta` that carries a `computed`
    spec — server-authoritative: any user-supplied value for a computed
    name is discarded in favor of the resolved value.

    Missing or unparseable source values resolve to "" (empty string) so
    that generation/preview with a partially-filled form never crashes.
    Values that ARE parseable but are outside a function's supported domain
    (e.g. a negative amount for number_to_words) raise
    `ComputedVariableError` — this is a genuine validation failure, not a
    "not filled in yet" case.
    """
    result: dict[str, str] = dict(user_values)

    for entry in variables_meta or []:
        computed = _get(entry, "computed")
        if not computed:
            continue

        name = _get(entry, "name")
        kind = _get(computed, "kind")
        source = _get(computed, "source")
        source_value = result.get(source)

        if kind == "formula":
            operator = _get(computed, "operator")
            operand = _get(computed, "operand")
            result[name] = _compute_formula(source_value, operator, operand)
        elif kind == "function":
            function = _get(computed, "function")
            result[name] = _compute_function(function, source_value)
        else:
            raise ComputedVariableError(f"Tipo de variable calculada desconocido: '{kind}'")

    return result


def computed_variable_names(variables_meta: list[dict] | None) -> set[str]:
    """Return the set of variable names that carry a `computed` spec.

    Used to exclude computed variables from any fillable/required-count
    logic (e.g. bulk Excel column headers) — the user never supplies these,
    the server always resolves them.
    """
    names: set[str] = set()
    for entry in variables_meta or []:
        if _get(entry, "computed"):
            names.add(_get(entry, "name"))
    return names
