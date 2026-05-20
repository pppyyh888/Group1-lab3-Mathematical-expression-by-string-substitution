# GROUP 1 - Lab 3 - Variant 2 - Mathematical Expression by String Substitution

## Description

This project contains an interpreter for mathematical expressions based on
repeated string substitution for Lab 3 of the Computational Process
Organization course.

The main goal of this laboratory work is to implement a basic model of
computation. The selected variant evaluates expressions by repeatedly finding
small reducible parts of an expression string, replacing them with calculated
values, and recording the complete substitution trace.

## Project Structure

- `expression_substitution.py` - implementation of the expression
  substitution interpreter
- `expression_substitution_test.py` - unit tests and property-based tests
- `requirements.txt` - project dependency list
- `README.md` - project description and design notes

## Contribution

- Pan Yuehao - implementation, testing, and documentation
- Pan Xuanting - lab requirements check, summarize

## Features

- Mathematical expression interpreter implementation
- String-substitution evaluation model
- Input language based on expression strings
- Support for integer and floating-point numbers
- Support for scientific notation
- Support for variables
- Support for parentheses
- Support for binary arithmetic operations
- Support for `+`, `-`, `*`, `/`, and `^`
- Support for built-in mathematical functions
- Support for user-defined functions
- Runtime error handling with custom exception classes
- Detailed error messages for invalid expressions
- Substitution trace for every evaluation step
- Markdown trace visualization
- GraphViz DOT trace visualization
- Python `logging` integration
- Delegation-based operation dispatch
- Aspect-oriented input validation with decorators
- Public API validation for expression, variables, functions, and step limit
- Unit tests
- Property-Based Testing with Hypothesis
- Tests for simple arithmetic expressions
- Tests for variables and function calls
- Tests for complex expressions
- Tests for runtime errors and corner cases
- Tests for logging and trace visualization

## Changelog

- Initial project setup from course template
- Added mathematical expression substitution interpreter
- Added string-substitution evaluation process
- Added input language for arithmetic expressions
- Added variable substitution support
- Added built-in mathematical functions
- Added user-defined function support
- Added custom exception classes for runtime errors
- Added substitution trace data structures
- Added Markdown and GraphViz DOT trace visualization
- Added Python logging for evaluation steps
- Added delegation-based binary operation handling
- Added aspect-oriented input validation decorators
- Added unit tests for main interpreter features
- Added complex example test for the expression substitution variant
- Added corner case tests for invalid syntax and runtime errors
- Added Property-Based Testing for arithmetic properties
- Updated README for Lab 3

## Design Notes

This project implements Lab 3 as a basic model of computation. The selected
variant represents a computational process as repeated rewriting of a
mathematical expression string. Each evaluation step finds a reducible part of
the current string and replaces it with the calculated result.

The input language is intentionally small. It supports numeric values,
variables, parentheses, arithmetic operations, and function calls. This keeps
the interpreter focused on the laboratory goal and avoids building a full
programming language.

The implementation does not use Python string evaluation. It does not call
`eval` or `exec`. Instead, it tokenizes flat numeric fragments and reduces one
operation at a time according to operator precedence.

The interpreter records each substitution in a `SubstitutionStep` object. The
complete result is returned as an `EvaluationResult` object. This object stores
the final numeric value, the final expression string, and the full trace of the
computational process.

The trace is also used for visualization. The result can be represented as a
Markdown table or as a GraphViz DOT graph. These views show how the original
expression changes step by step until the final value is reached.

Binary operations and function calls are selected by delegation. Operation and
function objects provide matching and execution behavior. This avoids direct
switch-style implementation of operation semantics in the main interpreter
logic.

Input data control is implemented in an aspect-oriented style with decorators.
Public evaluation methods validate expression type, non-empty expressions,
variables, user-defined functions, and the maximum number of substitution
steps before running the interpreter.

Runtime errors are represented by custom exception classes. The interpreter
reports unknown variables, unknown functions, invalid syntax, invalid function
calls, division by zero, and exhausted evaluation limits with detailed error
messages.

The tests include ordinary unit tests and Property-Based Testing. Unit tests
cover simple examples, the complex variant expression, trace contents,
visualization output, logging, input validation, and corner cases. Property-
Based Testing checks arithmetic properties over many automatically generated
integer inputs.
