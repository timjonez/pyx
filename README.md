# Pyx - JSX-like Syntax for Python

A lightweight transpiler that brings JSX-like syntax to Python, generating HTML strings. Write familiar-looking components with Python types and transpile them to standard Python.

## Features

- **JSX-like syntax** in `.pyx` files
- **Variable interpolation** with automatic HTML escaping
- **For loops** inside JSX blocks
- **Conditional rendering** with `if`/`else`
- **F-string support** inside expressions
- **Python type annotations** fully preserved
- **Server-side HTML rendering** - outputs plain HTML strings

## Quick Start

Write a `.pyx` file:

```python
def greeting(name: str) -> str:
    return (
        <div class="greeting">
            <h1>Hello, {name}!</h1>
        </div>
    )

def todo_list(items: list[str]) -> str:
    return (
        <ul>
            for item in items:
                <li>{item}</li>
        </ul>
    )
```

Transpile it:

```bash
python -m pyx.cli myfile.pyx
# Generates myfile.py
```

Or use the API:

```python
from pyx.transpiler import transpile

python_code = transpile(pyx_source)
```

## Syntax

### Elements

```python
def simple():
    return (
        <div>
            <h1>Title</h1>
            <p>Content</p>
        </div>
    )
```

### Variable Interpolation

```python
def dynamic(title: str, content: str) -> str:
    return (
        <div>
            <h1>{title}</h1>
            <p>{content}</p>
        </div>
    )
```

Values are automatically HTML-escaped.

### For Loops

```python
def list_items():
    items = ["apple", "banana", "cherry"]
    return (
        <ul>
            for item in items:
                <li>{item}</li>
        </ul>
    )
```

### Conditionals

```python
def filtered_list():
    return (
        <div>
            for i in range(10):
                if i % 2 == 0:
                    continue
                <span>Odd: {i}</span>
        </div>
    )
```

### F-strings

```python
def formatted(name: str, age: int) -> str:
    return (
        <div>
            <p>{f"Hello {name}, you are {age} years old"}</p>
        </div>
    )
```

### Nested Components

Call component functions directly inside JSX blocks — no brackets needed:

```python
def card(title: str, children: str = "") -> str:
    return (
        <div class="card">
            <h2>{title}</h2>
            <div class="card-body">{children}</div>
        </div>
    )

def alert(message: str, level: str = "info") -> str:
    return (
        <div class={f"alert alert-{level}"}>
            <strong>{message}</strong>
        </div>
    )

def page() -> str:
    return (
        <div class="container">
            <h1>My Page</h1>
            card(title="Welcome", children="Hello World")
            alert(message="Something happened!", level="warning")
        </div>
    )

# Components in loops work too:
def user_card(name: str, email: str) -> str:
    return (
        <div class="user-card">
            <h3>{name}</h3>
            <p>{email}</p>
        </div>
    )

def user_list(users: list[dict]) -> str:
    return (
        <div class="user-list">
            for user in users:
                user_card(name=user["name"], email=user["email"])
        </div>
    )
```

Component calls are rendered inline — they can appear before, between, or after HTML tags.

## How It Works

1. **Write** `.pyx` files with JSX-like syntax inside `return (...)` or assignment statements
2. **Transpile** with `pyx.cli` or the `transpile()` function
3. **Run** the generated `.py` files - they produce HTML strings using a simple `_buf` list + `join()` pattern

## Project Structure

```
pyx/
  transpiler.py    # Core .pyx -> .py transpiler
  runtime.py       # _escape() helper for HTML escaping
  cli.py           # Command-line interface
examples/
  demo.pyx         # Example pyx file
tests/
  test_transpiler.py  # Test suite
```

## License

MIT
