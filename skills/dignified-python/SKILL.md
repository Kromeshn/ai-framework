---
name: dignified-python
description: Философия и правила написания Python-кода (Dignified Python). Используй когда пишешь или редактируешь .py файлы.
---

# Dignified Python: Rules for LLM Code Generation

**Philosophy**: Write boring, explicit, local code. Resist abstraction. Optimize for clarity over cleverness.
---

## Core Principles

### 1. Boring is Better Than Clever
- Prefer simple functions over classes
- Prefer explicit code over "elegant" abstractions
- Prefer straightforward solutions over architectural patterns
- If it feels clever, it's probably wrong

### 2. Explicit is Better Than Magic
- No metaclasses
- No dynamic code generation
- No complex decorators (except standard library: @property, @cache, @dataclass)
- No "smart" factories or registry patterns

### 3. Local is Better Than Abstract
- Write code for the specific problem, not future problems
- Do NOT create abstractions without explicit user request
- Do NOT design "extensible" systems unless required
- Keep logic close to where it's used

### 4. Minimize Changes
- Do NOT refactor working code unless explicitly asked
- Do NOT add "improvements" that weren't requested
- Do NOT change function signatures without clear reason
- Keep changes focused and minimal

---

## Operating Discipline

These behavioral rules apply before and during every Python edit. They bias
toward caution over speed — for trivial tasks, use judgment.

### 1. Think Before Coding
- State assumptions explicitly before implementation.
- If the request has multiple valid interpretations, surface them instead of
  silently picking one.
- If a simpler approach exists, say so and prefer it.
- If a requirement is unclear enough to affect correctness, stop and ask.

### 2. Simplicity First
- Write the minimum code that solves the requested problem.
- Do not add speculative features, abstractions, configurability, or
  "future-proofing".
- Do not add error handling for impossible scenarios.
- If a solution feels larger than the problem, simplify before continuing.
- Test: would a senior engineer call this overcomplicated? If yes, simplify.

### 3. Surgical Changes
- Touch only lines that trace directly to the user's request.
- Match the existing local style, even when you would normally write it
  differently.
- Do not refactor adjacent working code or clean up unrelated comments,
  formatting, or dead code.
- Remove only unused imports, variables, or functions introduced by your own
  change.
- If you notice unrelated dead code or design issues, mention them instead of
  changing them.

### 4. Goal-Driven Execution
- Define success criteria before implementation.
- Transform vague tasks into verifiable goals: "Add validation" -> "write tests
  for invalid inputs, then make them pass"; "Refactor X" -> "tests pass before
  and after".
- For multi-step work, state a brief plan:
  `1. [Step] -> verify: [check]`.
- For bugs, prefer a test or focused reproduction that fails before the fix and
  passes after it.
- Loop until the agreed checks pass or a concrete blocker is reached.

---

## The Ten Rules

### Rule 1: Look Before You Leap (LBYL)

**CRITICAL**: Check conditions proactively. Do NOT use exceptions for control flow.

```python
# WRONG: Exception as control flow
try:
    value = mapping[key]
    process(value)
except KeyError:
    pass

# CORRECT: Check first
if key in mapping:
    value = mapping[key]
    process(value)
```

**Exceptions are acceptable only when**:
- At error boundaries with external systems
- Third-party APIs force exception handling
- Adding context before re-raising

### Rule 2: Never Swallow Exceptions

**CRITICAL**: Do NOT hide failures.

```python
# WRONG: Silent exception swallowing
try:
    risky_operation()
except:
    pass

# CORRECT: Let exceptions bubble up
risky_operation()
```

If you catch an exception, you MUST either:
- Re-raise it
- Log it with full context
- Convert it to a domain-specific error

### Rule 3: Magic Methods Must Be O(1)

`__len__`, `__bool__`, `__contains__`, `__getitem__` must run in constant time.

```python
# WRONG: __len__ iterating
def __len__(self) -> int:
    return sum(1 for _ in self._items)

# CORRECT: O(1) lookup
def __len__(self) -> int:
    return self._count
```

**Same applies to @property**: No I/O, no expensive computation.

### Rule 4: Check Existence Before Resolution

With `pathlib`, always check `.exists()` before `.resolve()` or `.is_relative_to()`.

```python
# WRONG: Can raise OSError
path_resolved = path.resolve()

# CORRECT: Check first
if path.exists():
    path_resolved = path.resolve()
```

### Rule 5: Defer Import-Time Computation

Module-level code runs at import. This causes:
- Slow startup
- Test brittleness
- Circular import issues
- Unpredictable side effects

```python
# WRONG: Computed at import
SESSION_FILE = Path("scratch/current-session-id")

# CORRECT: Defer with @cache
from functools import cache

@cache
def _session_file_path() -> Path:
    return Path("scratch/current-session-id")
```

### Rule 6: Verify Your Casts at Runtime

`typing.cast()` is compile-time only. It performs NO runtime verification.

```python
# WRONG: Blind cast
cast(dict[str, Any], doc)["key"] = value

# CORRECT: Assert before cast
assert isinstance(doc, MutableMapping), f"Expected MutableMapping, got {type(doc)}"
cast(dict[str, Any], doc)["key"] = value
```

**Skip assertion only when**:
- You just performed a type guard
- Performance-critical hot path (with documented justification)

### Rule 7: Use Literal Types for Fixed Values

When strings represent fixed valid values, use `Literal`.

```python
# WRONG: Bare strings (typos go unnoticed)
status = "complte"  # Typo!

# CORRECT: Literal type
from typing import Literal

Status = Literal["complete", "pending", "failed"]
status: Status = "complete"  # Typo caught by type checker!
```

**Use Literal when**:
- String is compared with `==` or `in`
- Fixed set of valid values exists
- Typo would cause a bug

### Rule 8: Declare Variables Close to Use

Variables should be declared as close as possible to where they're used.

```python
# WRONG: Early declaration
def process(ctx, items):
    result_path = compute_path(ctx)
    # ... 20 lines of other logic ...
    save(data, result_path)

# CORRECT: Inline at use
def process(ctx, items):
    # ... other logic ...
    save(data, compute_path(ctx))
```

**Exception**: Variable used multiple times or when inlining hurts readability.

### Rule 9: Keyword Arguments for Complex Functions

Functions with 5+ parameters MUST use keyword-only arguments.

```python
# WRONG: Positional chaos
response = fetch(url, 30.0, 3, {"Accept": "json"}, token)

# CORRECT: Keyword-only after first param
def fetch(
    url: str,
    *,
    timeout: float,
    retries: int,
    headers: dict[str, str],
    auth_token: str,
) -> Response:
    ...

response = fetch(
    url,
    timeout=30.0,
    retries=3,
    headers={"Accept": "json"},
    auth_token=token,
)
```

Use `*` separator after the first positional parameter.

### Rule 10: Default Values Are Dangerous

Avoid default parameter values unless absolutely necessary.

```python
# DANGEROUS: Caller forgets encoding
def read_file(path: Path, encoding: str = "utf-8") -> str:
    return path.read_text(encoding=encoding)

content = read_file(latin1_file)  # Bug! Wrong encoding

# SAFER: Require explicit choice
def read_file(path: Path, encoding: str) -> str:
    return path.read_text(encoding=encoding)

content = read_file(latin1_file, encoding="latin-1")
```

**Acceptable uses**:
- Default correct for 95%+ of callers
- Temporary backwards compatibility

**If default never overridden**: Eliminate parameter or hardcode value.

---

## Code Style Standards

### Type Hints
**REQUIRED**: Always use type hints for function arguments and return values.

```python
def process_data(input_path: str, threshold: float = 0.8) -> dict[str, Any]:
    ...
```

### PEP 8 Compliance
- 4 spaces for indentation
- 88 character line length
- `snake_case` for functions/variables
- `PascalCase` for classes
- `UPPER_CASE` for constants

### Import Organization
1. Standard library
2. Third-party libraries
3. Local application imports

Use Ruff to auto-format.

---

## Quality Tools (optional)

Use only if already configured in the project. Do NOT install or create `src/`, `tests/`, `pyproject.toml` unless explicitly asked.

```bash
ruff check --fix .
ruff format .
mypy main.py   # run against the actual file, not assumed src/
pytest         # only if tests/ exists
```

---

## Error Handling

### Use Context Managers
**ALWAYS** use `with` for resources:

```python
# Files
with open(filepath, encoding='utf-8') as f:
    data = json.load(f)

# NEVER
f = open(filepath)
data = json.load(f)
f.close()
```

### Catch Specific Exceptions
```python
# WRONG: Bare except
try:
    data = json.load(f)
except:
    data = {}

# CORRECT: Specific exception
try:
    data = json.load(f)
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON: {e}")
    raise
```

---

## Logging

Use Python's `logging` module:

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed diagnostic")
logger.info("Confirmation things working")
logger.warning("Unexpected but handled")
logger.error("Serious problem")
logger.critical("System may fail")
```

Configure once at application entry:
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## Testing

### Test-Driven Development
1. Write test describing expected behavior
2. Run test (should fail)
3. Write minimal code to pass
4. Refactor if needed
5. Repeat

### Test Structure
```python
def test_function_name():
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value
```

**Target**: >80% coverage on critical paths.

---

## Data Processing

### Files
- Validate existence before reading
- Explicit encoding: `open(file, encoding='utf-8')`
- Always use context managers

### Excel
- Use `pandas` for data manipulation
- Use `openpyxl` for formatting
- Handle missing data gracefully

### JSON
- Validate structure after loading
- Handle `JSONDecodeError` explicitly
- Consider Pydantic for validation

---

## Performance

### General
- Use built-in functions (they're optimized)
- List comprehensions for simple transformations
- Generators for large datasets
- Profile before optimizing

### Data Processing
- Use `pandas` for large datasets
- Avoid row-by-row DataFrame iteration
- Use vectorized operations

---

## Security

- **NEVER** commit secrets, API keys, passwords
- Use environment variables for sensitive data
- Use `.env` files (add to `.gitignore`)
- Load with `python-dotenv`

```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("API_KEY")
```

---

## Documentation

### Docstrings (Google Style)
```python
def process_document(doc_path: str, options: dict) -> dict:
    """Process document and extract structured data.

    Args:
        doc_path: Path to document file
        options: Processing options dictionary

    Returns:
        Dictionary containing extracted fields

    Raises:
        FileNotFoundError: If document doesn't exist
        ValueError: If document format invalid
    """
    ...
```

### README.md Requirements
- Project description
- Installation instructions
- Usage examples
- Development setup

---

## When to Ask for Clarification

**ASK** when:
- Requirements are ambiguous
- Multiple implementation approaches exist
- Tradeoffs need consideration
- Project-specific decisions needed

**DO NOT** make architectural decisions without user input.

---

## Workflow

1. **Understand** - Read requirements carefully
2. **Plan** - Outline approach before coding
3. **Implement** - Write code following these rules
4. **Test** - Write and run tests
5. **Validate** - Run linters and type checkers
6. **Document** - Add docstrings
7. **Review** - Verify code quality

---

## Anti-Patterns to Avoid

### DO NOT:
- Create classes when functions suffice
- Add abstraction layers "for extensibility"
- Implement design patterns unless explicitly needed
- Refactor working code without being asked
- Add features that weren't requested
- Use inheritance when composition works
- Create "base classes" or "abstract interfaces" prematurely
- Implement generic solutions for specific problems

### DO:
- Write the simplest code that solves the problem
- Add complexity only when explicitly required
- Keep code changes minimal and focused
- Ask before making architectural decisions

---

**Remember**: These rules exist to prevent common LLM mistakes. When in doubt, choose boring over clever, explicit over magic, and local over abstract.

