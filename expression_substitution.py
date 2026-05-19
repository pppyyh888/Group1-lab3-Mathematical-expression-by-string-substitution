"""Expression interpreter based on repeated string substitution.

The module implements Lab 3 variant 2: mathematical expression by string
substitution.  The interpreter repeatedly finds the smallest reducible part of
an expression string, replaces it with the calculated value, and stores every
replacement in a trace.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from functools import wraps
import logging
import math
import re
from typing import Callable, List, Mapping, Optional, Sequence, Tuple, Union
from typing import TypeVar, cast

NumberLike = Union[int, float]
NumericFunction = Callable[..., NumberLike]
F = TypeVar("F", bound=Callable[..., object])

LOGGER = logging.getLogger(__name__)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ExpressionError(Exception):
    """Base class for all expression interpreter errors."""


class ExpressionValidationError(ExpressionError):
    """Raised when public API arguments have invalid types or values."""


class ExpressionSyntaxError(ExpressionError):
    """Raised when an input expression has invalid syntax."""


class UnknownVariableError(ExpressionError):
    """Raised when an expression contains an unknown variable."""


class UnknownFunctionError(ExpressionError):
    """Raised when an expression contains an unknown function."""


class FunctionCallError(ExpressionError):
    """Raised when a function call cannot be completed correctly."""


class DivisionByZeroExpressionError(ExpressionError):
    """Raised when a division operation receives zero as the divisor."""


class EvaluationLimitError(ExpressionError):
    """Raised when evaluation does not finish in the configured step limit."""


@dataclass(frozen=True)
class SubstitutionStep:
    """Single replacement performed by the interpreter."""

    before: str
    target: str
    replacement: str
    after: str
    reason: str


@dataclass(frozen=True)
class EvaluationResult:
    """Result of expression evaluation with a complete substitution trace."""

    value: float
    final_expression: str
    trace: Tuple[SubstitutionStep, ...]

    def trace_as_markdown(self) -> str:
        """Return the substitution trace as a markdown table."""
        header = "| Step | Target | Replacement | Reason | Result |"
        separator = "| --- | --- | --- | --- | --- |"
        rows = [header, separator]
        for index, step in enumerate(self.trace, start=1):
            rows.append(
                "| {0} | `{1}` | `{2}` | {3} | `{4}` |".format(
                    index,
                    _escape_markdown(step.target),
                    _escape_markdown(step.replacement),
                    _escape_markdown(step.reason),
                    _escape_markdown(step.after),
                )
            )
        return "\n".join(rows)

    def trace_as_dot(self) -> str:
        """Return the substitution trace as a GraphViz DOT graph."""
        lines = ["digraph substitution_trace {", "  rankdir=LR;"]
        if not self.trace:
            lines.append('  n0 [label="{}"]'.format(self.final_expression))
            lines.append("}")
            return "\n".join(lines)

        lines.append('  n0 [label="{}"];'.format(
            _escape_dot(self.trace[0].before)
        ))
        for index, step in enumerate(self.trace, start=1):
            lines.append('  n{0} [label="{1}"];'.format(
                index,
                _escape_dot(step.after),
            ))
            label = "{} -> {}".format(step.target, step.replacement)
            lines.append('  n{0} -> n{1} [label="{2}"];'.format(
                index - 1,
                index,
                _escape_dot(label),
            ))
        lines.append("}")
        return "\n".join(lines)


@dataclass(frozen=True)
class _Replacement:
    start: int
    end: int
    replacement: str
    reason: str


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class _EvaluationContext:
    variables: Mapping[str, NumberLike]
    functions: Sequence["FunctionDelegate"]


class BinaryOperation:
    """Base class for binary operations selected by delegation."""

    symbol = ""
    precedence = 0

    def matches(self, symbol: str) -> bool:
        """Return True when this object handles the operation symbol."""
        return symbol == self.symbol

    def apply(self, left: float, right: float) -> float:
        """Apply the operation to two values."""
        raise NotImplementedError


class AddOperation(BinaryOperation):
    """Addition operation."""

    symbol = "+"
    precedence = 1

    def apply(self, left: float, right: float) -> float:
        """Return the sum of two values."""
        return left + right


class SubtractOperation(BinaryOperation):
    """Subtraction operation."""

    symbol = "-"
    precedence = 1

    def apply(self, left: float, right: float) -> float:
        """Return the difference between two values."""
        return left - right


class MultiplyOperation(BinaryOperation):
    """Multiplication operation."""

    symbol = "*"
    precedence = 2

    def apply(self, left: float, right: float) -> float:
        """Return the product of two values."""
        return left * right


class DivideOperation(BinaryOperation):
    """Division operation."""

    symbol = "/"
    precedence = 2

    def apply(self, left: float, right: float) -> float:
        """Return the quotient of two values."""
        if right == 0:
            raise DivisionByZeroExpressionError(
                "Division by zero while evaluating {0} / {1}".format(
                    left,
                    right,
                )
            )
        return left / right


class PowerOperation(BinaryOperation):
    """Power operation."""

    symbol = "^"
    precedence = 3

    def apply(self, left: float, right: float) -> float:
        """Return left raised to the power of right."""
        try:
            return math.pow(left, right)
        except ValueError as error:
            raise ExpressionError(
                "Invalid power operation {0} ^ {1}: {2}".format(
                    left,
                    right,
                    error,
                )
            ) from error


class FunctionDelegate:
    """Base class for function calls selected by delegation."""

    def matches(self, name: str) -> bool:
        """Return True when this object handles the function name."""
        raise NotImplementedError

    def apply(self, args: Tuple[float, ...]) -> float:
        """Apply the function to numeric arguments."""
        raise NotImplementedError


@dataclass(frozen=True)
class NamedFunction(FunctionDelegate):
    """Function delegate with an optional fixed arity."""

    name: str
    function: NumericFunction
    arity: Optional[int] = None

    def matches(self, name: str) -> bool:
        """Return True when the requested name is this function name."""
        return name == self.name

    def apply(self, args: Tuple[float, ...]) -> float:
        """Call the wrapped Python function with checked arguments."""
        if self.arity is not None and len(args) != self.arity:
            raise FunctionCallError(
                "Function '{0}' expects {1} argument(s), got {2}".format(
                    self.name,
                    self.arity,
                    len(args),
                )
            )
        try:
            result = self.function(*args)
        except TypeError as error:
            raise FunctionCallError(
                "Invalid call to function '{0}' with {1} argument(s): {2}"
                .format(self.name, len(args), error)
            ) from error
        except ValueError as error:
            raise FunctionCallError(
                "Function '{0}' failed for arguments {1}: {2}".format(
                    self.name,
                    args,
                    error,
                )
            ) from error
        except Exception as error:
            raise FunctionCallError(
                "Function '{0}' failed for arguments {1}: {2}".format(
                    self.name,
                    args,
                    error,
                )
            ) from error
        return _checked_float(result, "function '{}'".format(self.name))


def _validate_evaluate_arguments(method: F) -> F:
    """Validate public evaluate-like method arguments before execution."""

    @wraps(method)
    def wrapper(
        self: object,
        expression: object,
        variables: Optional[Mapping[str, NumberLike]] = None,
        functions: Optional[Mapping[str, NumericFunction]] = None,
        max_steps: int = 1000,
    ) -> object:
        _validate_expression(expression)
        _validate_variables_mapping(variables)
        _validate_functions_mapping(functions)
        if not isinstance(max_steps, int) or isinstance(max_steps, bool):
            raise ExpressionValidationError("max_steps must be a positive int")
        if max_steps <= 0:
            raise ExpressionValidationError("max_steps must be a positive int")
        return method(self, expression, variables, functions, max_steps)

    return cast(F, wrapper)


class ExpressionSubstitutionInterpreter:
    """Interpreter for mathematical expressions by string substitution."""

    def __init__(
        self,
        functions: Optional[Mapping[str, NumericFunction]] = None,
    ) -> None:
        """Create an interpreter with built-in and user-defined functions."""
        _validate_functions_mapping(functions)
        self._operations: Tuple[BinaryOperation, ...] = (
            AddOperation(),
            SubtractOperation(),
            MultiplyOperation(),
            DivideOperation(),
            PowerOperation(),
        )
        self._base_functions: Tuple[FunctionDelegate, ...] = (
            NamedFunction("sin", math.sin, 1),
            NamedFunction("cos", math.cos, 1),
            NamedFunction("tan", math.tan, 1),
            NamedFunction("sqrt", math.sqrt, 1),
            NamedFunction("log", math.log, 1),
            NamedFunction("exp", math.exp, 1),
            NamedFunction("abs", lambda value: abs(value), 1),
        )
        self._user_functions = _make_user_functions(functions)

    @_validate_evaluate_arguments
    def evaluate(
        self,
        expression: str,
        variables: Optional[Mapping[str, NumberLike]] = None,
        functions: Optional[Mapping[str, NumericFunction]] = None,
        max_steps: int = 1000,
    ) -> EvaluationResult:
        """Evaluate an expression and return value plus substitution trace."""
        current = _normalize_expression(expression)
        context = _EvaluationContext(
            variables={} if variables is None else dict(variables),
            functions=self._all_functions(functions),
        )
        trace: List[SubstitutionStep] = []
        LOGGER.info("Start expression evaluation: %s", current)
        _ensure_parentheses_are_balanced(current)

        for _ in range(max_steps):
            if _is_number_literal(current):
                value = _checked_float(float(current), "final expression")
                LOGGER.info("Evaluation finished: %s", current)
                return EvaluationResult(value, current, tuple(trace))

            replacement = self._find_replacement(current, context)
            before = current
            current = (
                current[:replacement.start]
                + replacement.replacement
                + current[replacement.end:]
            )
            step = SubstitutionStep(
                before=before,
                target=before[replacement.start:replacement.end],
                replacement=replacement.replacement,
                after=current,
                reason=replacement.reason,
            )
            trace.append(step)
            LOGGER.info(
                "Replace %s with %s (%s): %s",
                step.target,
                step.replacement,
                step.reason,
                step.after,
            )
            _ensure_parentheses_are_balanced(current)
            if _is_number_literal(current):
                value = _checked_float(float(current), "final expression")
                LOGGER.info("Evaluation finished: %s", current)
                return EvaluationResult(value, current, tuple(trace))

        raise EvaluationLimitError(
            "Evaluation did not finish after {0} substitution steps: {1}"
            .format(max_steps, current)
        )

    @_validate_evaluate_arguments
    def evaluate_value(
        self,
        expression: str,
        variables: Optional[Mapping[str, NumberLike]] = None,
        functions: Optional[Mapping[str, NumericFunction]] = None,
        max_steps: int = 1000,
    ) -> float:
        """Evaluate an expression and return only the numeric result."""
        return self.evaluate(expression, variables, functions, max_steps).value

    def _all_functions(
        self,
        extra_functions: Optional[Mapping[str, NumericFunction]],
    ) -> Tuple[FunctionDelegate, ...]:
        """Combine built-in, constructor-level, and call-level functions."""
        return (
            self._base_functions
            + self._user_functions
            + _make_user_functions(extra_functions)
        )

    def _find_replacement(
        self,
        expression: str,
        context: _EvaluationContext,
    ) -> _Replacement:
        """Find the next valid string substitution in the expression."""
        variable = _find_variable_replacement(expression, context)
        if variable is not None:
            return variable

        function = _find_function_replacement(expression, context)
        if function is not None:
            return function

        parentheses = self._find_parentheses_replacement(expression)
        if parentheses is not None:
            return parentheses

        top_level = self._find_numeric_replacement(
            expression,
            0,
            len(expression),
        )
        if top_level is not None:
            return top_level

        unknown_function = _find_first_function_name(expression)
        if unknown_function is not None:
            raise UnknownFunctionError(
                "Unknown or invalid function call '{0}' in expression '{1}'"
                .format(unknown_function, expression)
            )

        raise ExpressionSyntaxError(
            "Cannot find a reducible expression in '{0}'".format(expression)
        )

    def _find_parentheses_replacement(
        self,
        expression: str,
    ) -> Optional[_Replacement]:
        """Find a replacement inside the innermost parenthesized expression."""
        pair = _find_innermost_parentheses(expression)
        if pair is None:
            return None

        open_index, close_index = pair
        inside = expression[open_index + 1:close_index]
        function_name = _function_name_before(expression, open_index)
        if inside == "":
            if function_name is None:
                raise ExpressionSyntaxError(
                    "Empty parentheses in expression '{0}'".format(expression)
                )
            return None

        if function_name is None and _is_number_literal(inside):
            if _has_adjacent_value(expression, open_index, close_index + 1):
                raise ExpressionSyntaxError(
                    "Missing operator near parentheses in expression '{0}'"
                    .format(expression)
                )
            return _Replacement(
                start=open_index,
                end=close_index + 1,
                replacement=_format_number(float(inside)),
                reason="remove parentheses around a value",
            )

        inner_replacement = self._find_numeric_replacement(
            expression,
            open_index + 1,
            close_index,
        )
        if inner_replacement is not None:
            return inner_replacement

        raise ExpressionSyntaxError(
            "Cannot reduce parenthesized part '{0}' in expression '{1}'"
            .format(inside, expression)
        )

    def _find_numeric_replacement(
        self,
        expression: str,
        start: int,
        end: int,
    ) -> Optional[_Replacement]:
        """Find one arithmetic replacement inside expression[start:end]."""
        segment = expression[start:end]
        for part_start, part_end in _comma_separated_ranges(segment):
            absolute_start = start + part_start
            absolute_end = start + part_end
            part = expression[absolute_start:absolute_end]
            if part == "":
                raise ExpressionSyntaxError(
                    "Empty function argument in expression '{0}'".format(
                        expression,
                    )
                )
            if _is_number_literal(part):
                continue
            reduction = self._reduce_flat_numeric(part)
            if reduction is None:
                continue
            local_start, local_end, replacement = reduction
            return _Replacement(
                start=absolute_start + local_start,
                end=absolute_start + local_end,
                replacement=replacement,
                reason="arithmetic reduction",
            )
        return None

    def _reduce_flat_numeric(
        self,
        expression: str,
    ) -> Optional[Tuple[int, int, str]]:
        """Reduce one operation in a flat numeric expression."""
        if _contains_identifier_or_parentheses(expression):
            return None
        tokens = _tokenize_flat_numeric(expression)
        if len(tokens) == 1 and tokens[0].kind == "number":
            return None

        best_index = -1
        best_operation: Optional[BinaryOperation] = None
        for index, token in enumerate(tokens):
            if token.kind != "operator":
                continue
            operation = self._operation_for(token.text)
            if best_operation is None:
                best_index = index
                best_operation = operation
            elif operation.precedence > best_operation.precedence:
                best_index = index
                best_operation = operation

        if best_operation is None or best_index <= 0:
            return None
        if best_index + 1 >= len(tokens):
            raise ExpressionSyntaxError(
                "Missing right operand in '{0}'".format(expression)
            )

        left = tokens[best_index - 1]
        right = tokens[best_index + 1]
        if left.kind != "number" or right.kind != "number":
            raise ExpressionSyntaxError(
                "Invalid binary operation in '{0}'".format(expression)
            )

        left_value = _checked_float(float(left.text), "left operand")
        right_value = _checked_float(float(right.text), "right operand")
        result = best_operation.apply(left_value, right_value)
        result = _checked_float(result, "operation result")
        return left.start, right.end, _format_number(result)

    def _operation_for(self, symbol: str) -> BinaryOperation:
        """Return an operation object for a symbol using delegation."""
        for operation in self._operations:
            if operation.matches(symbol):
                return operation
        raise ExpressionSyntaxError("Unknown operator '{0}'".format(symbol))


def evaluate_expression(
    expression: str,
    variables: Optional[Mapping[str, NumberLike]] = None,
    functions: Optional[Mapping[str, NumericFunction]] = None,
    max_steps: int = 1000,
) -> EvaluationResult:
    """Evaluate an expression with a default interpreter instance."""
    interpreter = ExpressionSubstitutionInterpreter()
    return interpreter.evaluate(expression, variables, functions, max_steps)


def _validate_expression(expression: object) -> None:
    """Validate the expression argument."""
    if not isinstance(expression, str):
        raise ExpressionValidationError("expression must be a string")
    if expression.strip() == "":
        raise ExpressionValidationError("expression must not be empty")


def _validate_variables_mapping(
    variables: Optional[Mapping[str, NumberLike]],
) -> None:
    """Validate variables passed to the public API."""
    if variables is None:
        return
    if not isinstance(variables, MappingABC):
        raise ExpressionValidationError("variables must be a mapping")
    for name, value in variables.items():
        if not isinstance(name, str) or not _is_identifier(name):
            raise ExpressionValidationError(
                "variable names must be valid identifiers"
            )
        _checked_number_like(value, "variable '{}'".format(name))


def _validate_functions_mapping(
    functions: Optional[Mapping[str, NumericFunction]],
) -> None:
    """Validate function delegates passed to the public API."""
    if functions is None:
        return
    if not isinstance(functions, MappingABC):
        raise ExpressionValidationError("functions must be a mapping")
    for name, function in functions.items():
        if not isinstance(name, str) or not _is_identifier(name):
            raise ExpressionValidationError(
                "function names must be valid identifiers"
            )
        if not callable(function):
            raise ExpressionValidationError(
                "function '{}' must be callable".format(name)
            )


def _normalize_expression(expression: str) -> str:
    """Remove whitespace from the expression before substitutions."""
    return "".join(expression.split())


def _make_user_functions(
    functions: Optional[Mapping[str, NumericFunction]],
) -> Tuple[FunctionDelegate, ...]:
    """Convert a mapping of user functions into delegates."""
    if functions is None:
        return ()
    return tuple(
        NamedFunction(name, function, None)
        for name, function in functions.items()
    )


def _find_variable_replacement(
    expression: str,
    context: _EvaluationContext,
) -> Optional[_Replacement]:
    """Find the first variable that can be replaced with its value."""
    for match in _IDENTIFIER_RE.finditer(expression):
        name = match.group(0)
        if _is_identifier_part_of_number_exponent(expression, match):
            continue
        if match.end() < len(expression) and expression[match.end()] == "(":
            continue
        if _has_adjacent_value(expression, match.start(), match.end()):
            raise ExpressionSyntaxError(
                "Missing operator near variable '{0}' in expression '{1}'"
                .format(name, expression)
            )
        if name not in context.variables:
            raise UnknownVariableError(
                "Unknown variable '{0}' in expression '{1}'".format(
                    name,
                    expression,
                )
            )
        value = context.variables[name]
        return _Replacement(
            start=match.start(),
            end=match.end(),
            replacement=_format_number(float(value)),
            reason="variable substitution",
        )
    return None


def _has_adjacent_value(expression: str, start: int, end: int) -> bool:
    """Return True when a value is adjacent without an operator."""
    left_is_value = start > 0 and _can_end_value(expression[start - 1])
    right_is_value = (
        end < len(expression)
        and _can_start_value(expression[end])
    )
    return left_is_value or right_is_value


def _can_end_value(char: str) -> bool:
    """Return True when char may end a numeric expression value."""
    return char.isalnum() or char in "_.)"


def _can_start_value(char: str) -> bool:
    """Return True when char may start a numeric expression value."""
    return char.isalnum() or char in "_.("


def _is_identifier_part_of_number_exponent(
    expression: str,
    match: re.Match[str],
) -> bool:
    """Return True when a regex identifier is an exponent part."""
    name = match.group(0)
    if name[0] not in "eE" or match.start() == 0:
        return False
    previous = expression[match.start() - 1]
    if not (previous.isdigit() or previous == "."):
        return False
    if len(name) > 1:
        return name[1:].isdigit()
    return (
        match.end() + 1 < len(expression)
        and expression[match.end()] in "+-"
        and expression[match.end() + 1].isdigit()
    )


def _find_function_replacement(
    expression: str,
    context: _EvaluationContext,
) -> Optional[_Replacement]:
    """Find a function call whose arguments are already numeric values."""
    for open_index, close_index in _iter_parentheses_pairs(expression):
        name_info = _function_name_info_before(expression, open_index)
        if name_info is None:
            continue

        name_start, name = name_info
        args_text = expression[open_index + 1:close_index]
        args = _parse_ready_arguments(args_text)
        if args is None:
            continue

        delegate = _function_delegate_for(name, context.functions)
        if _has_adjacent_value(expression, name_start, close_index + 1):
            raise ExpressionSyntaxError(
                "Missing operator near function call '{0}' in expression '{1}'"
                .format(name, expression)
            )
        result = delegate.apply(args)
        return _Replacement(
            start=name_start,
            end=close_index + 1,
            replacement=_format_number(result),
            reason="function call",
        )
    return None


def _function_delegate_for(
    name: str,
    functions: Sequence[FunctionDelegate],
) -> FunctionDelegate:
    """Return a function delegate by asking every delegate to match."""
    for function in functions:
        if function.matches(name):
            return function
    raise UnknownFunctionError("Unknown function '{0}'".format(name))


def _parse_ready_arguments(args_text: str) -> Optional[Tuple[float, ...]]:
    """Return numeric function arguments when all arguments are ready."""
    if args_text == "":
        return ()
    args = []
    for start, end in _comma_separated_ranges(args_text):
        part = args_text[start:end]
        if part == "":
            raise ExpressionSyntaxError("Empty function argument")
        if not _is_number_literal(part):
            return None
        args.append(_checked_float(float(part), "function argument"))
    return tuple(args)


def _iter_parentheses_pairs(expression: str) -> Sequence[Tuple[int, int]]:
    """Return parenthesis pairs ordered from inner to outer."""
    stack = []
    pairs = []
    for index, char in enumerate(expression):
        if char == "(":
            stack.append(index)
        elif char == ")":
            if not stack:
                raise ExpressionSyntaxError(
                    "Unmatched ')' at position {0} in '{1}'".format(
                        index,
                        expression,
                    )
                )
            pairs.append((stack.pop(), index))
    if stack:
        raise ExpressionSyntaxError(
            "Unmatched '(' at position {0} in '{1}'".format(
                stack[-1],
                expression,
            )
        )
    return tuple(sorted(pairs, key=lambda pair: pair[1] - pair[0]))


def _find_innermost_parentheses(
    expression: str,
) -> Optional[Tuple[int, int]]:
    """Return the first innermost parenthesis pair."""
    pairs = _iter_parentheses_pairs(expression)
    if not pairs:
        return None
    return pairs[0]


def _ensure_parentheses_are_balanced(expression: str) -> None:
    """Raise a syntax error if parentheses are not balanced."""
    _iter_parentheses_pairs(expression)


def _function_name_before(
    expression: str,
    open_index: int,
) -> Optional[str]:
    """Return a function name directly before an opening parenthesis."""
    info = _function_name_info_before(expression, open_index)
    if info is None:
        return None
    return info[1]


def _function_name_info_before(
    expression: str,
    open_index: int,
) -> Optional[Tuple[int, str]]:
    """Return the start position and name before an opening parenthesis."""
    if open_index == 0:
        return None
    index = open_index - 1
    if not (expression[index].isalnum() or expression[index] == "_"):
        return None
    while index >= 0:
        char = expression[index]
        if not (char.isalnum() or char == "_"):
            break
        index -= 1
    name_start = index + 1
    name = expression[name_start:open_index]
    if not _is_identifier(name):
        return None
    return name_start, name


def _find_first_function_name(expression: str) -> Optional[str]:
    """Find the first function-looking name in an expression."""
    for match in _IDENTIFIER_RE.finditer(expression):
        if match.end() < len(expression) and expression[match.end()] == "(":
            return match.group(0)
    return None


def _comma_separated_ranges(expression: str) -> Sequence[Tuple[int, int]]:
    """Split expression by top-level commas and return index ranges."""
    ranges = []
    depth = 0
    start = 0
    for index, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            ranges.append((start, index))
            start = index + 1
    ranges.append((start, len(expression)))
    return tuple(ranges)


def _tokenize_flat_numeric(expression: str) -> Tuple[_Token, ...]:
    """Tokenize a numeric expression without identifiers or parentheses."""
    if expression == "":
        raise ExpressionSyntaxError("Empty numeric expression")

    tokens = []
    index = 0
    expect_number = True
    while index < len(expression):
        char = expression[index]
        if _starts_number(expression, index, expect_number):
            end = _read_number_end(expression, index, expect_number)
            tokens.append(_Token("number", expression[index:end], index, end))
            index = end
            expect_number = False
        elif char in "+-*/^" and not expect_number:
            tokens.append(_Token("operator", char, index, index + 1))
            index += 1
            expect_number = True
        else:
            raise ExpressionSyntaxError(
                "Unexpected token '{0}' at position {1} in '{2}'".format(
                    char,
                    index,
                    expression,
                )
            )

    if tokens and tokens[-1].kind == "operator":
        raise ExpressionSyntaxError(
            "Expression '{0}' ends with an operator".format(expression)
        )
    return tuple(tokens)


def _starts_number(expression: str, index: int, allow_sign: bool) -> bool:
    """Return True if a number literal starts at index."""
    char = expression[index]
    if char.isdigit() or char == ".":
        return True
    if char in "+-" and allow_sign and index + 1 < len(expression):
        next_char = expression[index + 1]
        return next_char.isdigit() or next_char == "."
    return False


def _read_number_end(expression: str, index: int, allow_sign: bool) -> int:
    """Return the end index of a number literal."""
    start = index
    if allow_sign and expression[index] in "+-":
        index += 1

    digits_before_dot = 0
    while index < len(expression) and expression[index].isdigit():
        index += 1
        digits_before_dot += 1

    digits_after_dot = 0
    if index < len(expression) and expression[index] == ".":
        index += 1
        while index < len(expression) and expression[index].isdigit():
            index += 1
            digits_after_dot += 1

    if digits_before_dot == 0 and digits_after_dot == 0:
        raise ExpressionSyntaxError(
            "Invalid number literal near '{0}'".format(expression[start:])
        )

    if index < len(expression) and expression[index] in "eE":
        exponent_start = index
        index += 1
        if index < len(expression) and expression[index] in "+-":
            index += 1
        exponent_digits = 0
        while index < len(expression) and expression[index].isdigit():
            index += 1
            exponent_digits += 1
        if exponent_digits == 0:
            raise ExpressionSyntaxError(
                "Invalid exponent near '{0}'".format(
                    expression[exponent_start:]
                )
            )

    return index


def _is_number_literal(value: str) -> bool:
    """Return True when the complete string is a finite number literal."""
    if value == "":
        return False
    try:
        end = _read_number_end(value, 0, True)
    except ExpressionSyntaxError:
        return False
    if end != len(value):
        return False
    try:
        number = float(value)
    except ValueError:
        return False
    return math.isfinite(number)


def _contains_identifier_or_parentheses(expression: str) -> bool:
    """Return True if flat numeric reduction is not applicable."""
    return "(" in expression or ")" in expression


def _is_identifier(name: str) -> bool:
    """Return True when name is a valid expression identifier."""
    return _IDENTIFIER_RE.fullmatch(name) is not None


def _checked_number_like(value: object, source: str) -> float:
    """Validate a user-provided numeric value and return it as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExpressionValidationError(
            "{} must be an int or float".format(source)
        )
    return _checked_float(float(value), source)


def _checked_float(value: NumberLike, source: str) -> float:
    """Validate an interpreter numeric result and return it as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExpressionError("{} produced a non-numeric value".format(source))
    number = float(value)
    if not math.isfinite(number):
        raise ExpressionError("{} produced a non-finite value".format(source))
    return number


def _format_number(value: float) -> str:
    """Format a float so it can be used again in the expression string."""
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "0"
    nearest_integer = round(value)
    if math.isclose(value, nearest_integer, abs_tol=1e-12):
        return str(nearest_integer)
    return format(value, ".15g")


def _escape_markdown(value: str) -> str:
    """Escape vertical bars for markdown table cells."""
    return value.replace("|", "\\|")


def _escape_dot(value: str) -> str:
    """Escape a string for a GraphViz DOT label."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
