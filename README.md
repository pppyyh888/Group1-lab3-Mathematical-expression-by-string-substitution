# GROUP 1 - Lab 3 - Variant 2 - Mathematical Expression by String Substitution

## Description

This project contains a small mathematical expression interpreter for Lab 3 of
the Computational Process Organization course.

The selected variant is mathematical expression by string substitution. The
interpreter receives an expression as a string, finds the next reducible part of
the expression, calculates it, and replaces that substring with the calculated
value. This process continues until the whole expression becomes one final
numeric value.

The project focuses on a simple, explicit model of computation. The execution
process is observable through a substitution trace and logging messages.

## Project Structure

- `expression_substitution.py` - implementation of the expression interpreter
- `expression_substitution_test.py` - unit tests and property-based tests
- `requirements.txt` - project dependency list
- `README.md` - project description and design notes

## Contribution

- Pan Yuehao - implementation, testing, and documentation
- Pan Xuanting - lab requirements check, summarize

## Input Language

The interpreter accepts mathematical expressions written as strings.

Supported syntax:

- numbers, including integers, decimal numbers, and scientific notation
- variables such as `a`, `b`, `x1`, and `total_value`
- binary operators: `+`, `-`, `*`, `/`, and `^`
- parentheses for explicit evaluation order
- built-in function calls such as `sin(0)` and `sqrt(4)`
- user-defined function calls such as `foo(1 + 2)`

Example expression:

```text
a + 2 - sin(-0.3) * (b - c)
```

The language does not support implicit multiplication. For example, `2a`,
`1(2)`, and `sin(0)2` are rejected as syntax errors.

## Features

- Mathematical expression evaluation by repeated string substitution
- Input expressions represented as strings
- Variable substitution
- Built-in mathematical functions
- User-defined functions
- Binary operations for addition, subtraction, multiplication, division, and
  power
- Parenthesized expression reduction
- Scientific notation support
- Explicit rejection of missing operators between adjacent values
- Custom exception classes for syntax, variable, function, division, and
  evaluation limit errors
- Detailed runtime error messages
- Execution trace with `before`, `target`, `replacement`, `after`, and `reason`
- Markdown trace visualization
- GraphViz DOT trace visualization
- Logging with the standard Python `logging` module
- Aspect-Oriented Programming (AOP) style public input validation
- Operation and function dispatch through delegation objects
- No use of Python `eval()` or `exec()`
- Unit tests
- Property-Based Testing (PBT) with Hypothesis
- Tests for simple examples, complex examples, corner cases, and errors

## Public Application Programming Interface

The main class is `ExpressionSubstitutionInterpreter`.

```python
from expression_substitution import ExpressionSubstitutionInterpreter

interpreter = ExpressionSubstitutionInterpreter()

result = interpreter.evaluate(
    "a + 2 - sin(-0.3) * (b - c)",
    variables={"a": 1, "b": 5, "c": 3},
)

print(result.value)
print(result.trace_as_markdown())
```

The module also provides a helper function for simple use cases.

```python
from expression_substitution import evaluate_expression

result = evaluate_expression("x + 1", variables={"x": 41})
print(result.value)
```

## Example Substitution Process

For this expression:

```text
a + 2 * (b - c)
```

with this input data:

```python
{"a": 1, "b": 5, "c": 3}
```

the interpreter performs substitutions similar to this process:

```text
a+2*(b-c)
1+2*(b-c)
1+2*(5-c)
1+2*(5-3)
1+2*2
1+4
5
```

Each step is stored in the trace as a `SubstitutionStep`.

## How to Run

Install project dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Run tests with coverage:

```bash
coverage run -m pytest
coverage report -m
```

Run static checks:

```bash
pycodestyle .
pyflakes .
mypy .
```

## Changelog

- Initial project setup from course template
- Added mathematical expression interpreter for Lab 3
- Added expression evaluation by string substitution
- Added variables and arithmetic operations
- Added parenthesized expression reduction
- Added built-in mathematical functions
- Added user-defined function support
- Added custom runtime error classes
- Added substitution trace data structures
- Added Markdown and GraphViz DOT trace visualization
- Added logging for the evaluation process
- Added Aspect-Oriented Programming style input validation
- Added checks for missing operators between adjacent values
- Added scientific notation support
- Added unit tests for simple and complex expressions
- Added tests for variables, functions, logging, trace, and visualization
- Added corner case tests for invalid syntax and runtime errors
- Added Property-Based Testing for arithmetic properties
- Updated README for Lab 3

## Design Notes

This project implements Lab 3 as a small interpreter for a restricted
mathematical expression language. The interpreter does not evaluate the input
string with Python evaluation tools. Instead, it repeatedly searches for the
next reducible substring and replaces it with a calculated value.

The main execution result is represented by `EvaluationResult`. It contains
the final numeric value, the final expression string, and the complete
substitution trace. Each trace entry is represented by `SubstitutionStep` and
records the expression before the replacement, the replaced substring, the
replacement value, the expression after the replacement, and the reason for the
replacement.

The interpreter uses delegation for operations and functions. Binary
operations are represented by subclasses of `BinaryOperation`. Function calls
are represented by `FunctionDelegate` objects. This keeps operation selection
separate from the main evaluation algorithm.

The evaluation strategy is intentionally simple. The interpreter first handles
variables, then function calls, then innermost parentheses, and then arithmetic
operations in flat numeric expressions. This order keeps the string
substitution process explicit and easy to trace.

Input data control is implemented in an aspect-oriented style. Public
evaluation methods are protected by validation decorators that check
expression type, empty expressions, variable mappings, function mappings, and
the evaluation step limit before interpretation starts.

Runtime errors are reported with custom exceptions. This makes failures more
specific than generic Python exceptions and helps tests verify error behavior
directly. Division by zero, unknown variables, unknown functions, syntax
errors, function call failures, and evaluation limit failures all have separate
exception classes.

The implementation rejects implicit multiplication and value concatenation.
Expressions such as `2a`, `1(2)`, and `sin(0)2` are treated as syntax errors.
This keeps the input language small and avoids ambiguous string replacement
results.

The test suite combines example-based unit tests and Property-Based Testing.
Unit tests check the required behavior directly. Property-Based Testing checks
general arithmetic properties over generated input values.
