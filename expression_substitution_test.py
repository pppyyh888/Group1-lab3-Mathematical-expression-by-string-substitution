"""Tests for the string-substitution expression interpreter."""

import logging
import math
from typing import Any, cast

from hypothesis import given
import hypothesis.strategies as st
import pytest

from expression_substitution import (
    DivisionByZeroExpressionError,
    EvaluationLimitError,
    ExpressionSubstitutionInterpreter,
    ExpressionSyntaxError,
    ExpressionValidationError,
    FunctionCallError,
    UnknownFunctionError,
    UnknownVariableError,
    evaluate_expression,
)


INTEGER_VALUES = st.integers(min_value=-100, max_value=100)
NON_ZERO_INTEGER_VALUES = st.integers(min_value=-100, max_value=100).filter(
    lambda value: value != 0
)


def assert_close(actual: float, expected: float) -> None:
    """Assert equality for floating-point calculation results."""
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)


def test_evaluate_simple_arithmetic_examples() -> None:
    """Interpreter should evaluate simple arithmetic expressions."""
    interpreter = ExpressionSubstitutionInterpreter()

    assert_close(interpreter.evaluate_value("1 + 2"), 3.0)
    assert_close(interpreter.evaluate_value("2 * 3 + 4"), 10.0)
    assert_close(interpreter.evaluate_value("2 * (3 + 4)"), 14.0)
    assert_close(interpreter.evaluate_value("2 ^ 3 + 1"), 9.0)


def test_evaluate_variables_by_substitution() -> None:
    """Variables should be substituted before arithmetic reduction."""
    interpreter = ExpressionSubstitutionInterpreter()
    result = interpreter.evaluate("a + b * c", {"a": 2, "b": 3, "c": 4})

    assert_close(result.value, 14.0)
    assert result.final_expression == "14"
    assert [step.replacement for step in result.trace[:3]] == ["2", "3", "4"]


def test_builtin_functions_are_supported() -> None:
    """Built-in mathematical functions should be callable by name."""
    interpreter = ExpressionSubstitutionInterpreter()

    assert_close(interpreter.evaluate_value("sin(0)"), 0.0)
    assert_close(interpreter.evaluate_value("cos(0)"), 1.0)
    assert_close(interpreter.evaluate_value("sqrt(4)"), 2.0)
    assert_close(interpreter.evaluate_value("abs(-5)"), 5.0)


def test_call_level_user_function_is_supported() -> None:
    """User functions should be accepted as call-level arguments."""
    interpreter = ExpressionSubstitutionInterpreter()
    result = interpreter.evaluate("foo(1 + 2) * 3", functions={
        "foo": lambda value: value * 42,
    })

    assert_close(result.value, 378.0)
    assert any(step.target == "foo(3)" for step in result.trace)


def test_constructor_level_user_function_is_supported() -> None:
    """User functions should be accepted by the interpreter constructor."""
    interpreter = ExpressionSubstitutionInterpreter(functions={
        "avg": lambda left, right: (left + right) / 2,
    })

    assert_close(interpreter.evaluate_value("avg(2, 6) + 1"), 5.0)


def test_complex_example_from_variant_description() -> None:
    """Interpreter should evaluate a complex expression with variables."""
    interpreter = ExpressionSubstitutionInterpreter()
    variables = {"a": 1, "b": 5, "c": 3}
    expression = "a + 2 - sin(-0.3) * (b - c)"

    result = interpreter.evaluate(expression, variables)
    expected = 1 + 2 - math.sin(-0.3) * (5 - 3)

    assert_close(result.value, expected)
    assert len(result.trace) > 1
    assert result.trace[0].before == "a+2-sin(-0.3)*(b-c)"
    assert result.trace[-1].after == result.final_expression


def test_public_function_evaluates_expression() -> None:
    """The module-level public helper should evaluate expressions."""
    result = evaluate_expression("x + 1", {"x": 41})

    assert_close(result.value, 42.0)


def test_trace_contains_all_substitution_details() -> None:
    """Trace entries should describe every performed replacement."""
    interpreter = ExpressionSubstitutionInterpreter()
    result = interpreter.evaluate("a + 2", {"a": 1})

    assert len(result.trace) == 2
    first_step = result.trace[0]
    assert first_step.before == "a+2"
    assert first_step.target == "a"
    assert first_step.replacement == "1"
    assert first_step.after == "1+2"
    assert first_step.reason == "variable substitution"


def test_markdown_trace_visualization() -> None:
    """Evaluation result should provide markdown trace visualization."""
    interpreter = ExpressionSubstitutionInterpreter()
    markdown = interpreter.evaluate("a + 2", {"a": 1}).trace_as_markdown()

    assert "| Step | Target | Replacement | Reason | Result |" in markdown
    assert "`a`" in markdown
    assert "variable substitution" in markdown


def test_dot_trace_visualization() -> None:
    """Evaluation result should provide GraphViz DOT visualization."""
    interpreter = ExpressionSubstitutionInterpreter()
    dot = interpreter.evaluate("1 + 2").trace_as_dot()

    assert dot.startswith("digraph substitution_trace")
    assert "rankdir=LR" in dot
    assert "1+2 -> 3" in dot


def test_logging_makes_evaluation_transparent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Interpreter should log start, substitution, and finish events."""
    interpreter = ExpressionSubstitutionInterpreter()

    with caplog.at_level(logging.INFO, logger="expression_substitution"):
        interpreter.evaluate("1 + 2")

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Start expression evaluation" in message
        for message in messages
    )
    assert any("Replace 1+2 with 3" in message for message in messages)
    assert any("Evaluation finished" in message for message in messages)


@pytest.mark.parametrize(
    ("expression", "error_type"),
    [
        ("x + 1", UnknownVariableError),
        ("missing(1)", UnknownFunctionError),
        ("1 / 0", DivisionByZeroExpressionError),
        ("1 +", ExpressionSyntaxError),
        ("(1 + 2", ExpressionSyntaxError),
        ("sin()", FunctionCallError),
    ],
)
def test_runtime_errors_are_reported_with_specific_exceptions(
    expression: str,
    error_type: type[Exception],
) -> None:
    """Invalid expressions should fail with detailed exception classes."""
    interpreter = ExpressionSubstitutionInterpreter()

    with pytest.raises(error_type) as exc_info:
        interpreter.evaluate(expression)

    assert str(exc_info.value)


@pytest.mark.parametrize(
    ("expression", "variables", "functions", "max_steps"),
    [
        ("", None, None, 1000),
        (123, None, None, 1000),
        ("a + 1", {"bad-name": 1}, None, 1000),
        ("a + 1", {"a": True}, None, 1000),
        ("f(1)", None, {"bad-name": lambda value: value}, 1000),
        ("f(1)", None, {"f": 42}, 1000),
        ("1 + 1", None, None, 0),
    ],
)
def test_aspect_oriented_input_validation_rejects_bad_public_arguments(
    expression: object,
    variables: object,
    functions: object,
    max_steps: int,
) -> None:
    """Public API decorators should reject bad types and values."""
    interpreter = ExpressionSubstitutionInterpreter()

    with pytest.raises(ExpressionValidationError):
        interpreter.evaluate(
            cast(Any, expression),
            cast(Any, variables),
            cast(Any, functions),
            max_steps,
        )


def test_evaluation_limit_is_reported() -> None:
    """Interpreter should report that max_steps was exhausted."""
    interpreter = ExpressionSubstitutionInterpreter()

    with pytest.raises(EvaluationLimitError):
        interpreter.evaluate("1 + 2", max_steps=1)


@given(INTEGER_VALUES, INTEGER_VALUES)
def test_pbt_addition_matches_python_arithmetic(left: int, right: int) -> None:
    """Property-based test: addition should match Python arithmetic."""
    interpreter = ExpressionSubstitutionInterpreter()
    result = interpreter.evaluate_value("left + right", {
        "left": left,
        "right": right,
    })

    assert_close(result, float(left + right))


@given(INTEGER_VALUES, INTEGER_VALUES)
def test_pbt_addition_is_commutative(left: int, right: int) -> None:
    """Property-based test: addition should be commutative."""
    interpreter = ExpressionSubstitutionInterpreter()
    variables = {"left": left, "right": right}

    first = interpreter.evaluate_value("left + right", variables)
    second = interpreter.evaluate_value("right + left", variables)

    assert_close(first, second)


@given(INTEGER_VALUES, INTEGER_VALUES)
def test_pbt_multiplication_is_commutative(left: int, right: int) -> None:
    """Property-based test: multiplication should be commutative."""
    interpreter = ExpressionSubstitutionInterpreter()
    variables = {"left": left, "right": right}

    first = interpreter.evaluate_value("left * right", variables)
    second = interpreter.evaluate_value("right * left", variables)

    assert_close(first, second)


@given(INTEGER_VALUES)
def test_pbt_subtracting_value_from_itself_returns_zero(value: int) -> None:
    """Property-based test: x - x should be zero."""
    interpreter = ExpressionSubstitutionInterpreter()

    result = interpreter.evaluate_value("x - x", {"x": value})

    assert_close(result, 0.0)


@given(NON_ZERO_INTEGER_VALUES)
def test_pbt_dividing_value_by_itself_returns_one(value: int) -> None:
    """Property-based test: x / x should be one for non-zero x."""
    interpreter = ExpressionSubstitutionInterpreter()

    result = interpreter.evaluate_value("x / x", {"x": value})

    assert_close(result, 1.0)
