"""Tests for pyx transpiler."""

from pyx.transpiler import transpile
from pyx.runtime import _escape


class TestSimpleElements:
    def test_simple_div(self):
        source = '''
def simple():
    return (
        <div>
            <h1>Title</h1>
            <p>Content</p>
        </div>
    )
'''
        result = transpile(source)
        # Execute and check
        ns = {"_escape": _escape}
        exec(result, ns)
        assert ns["simple"]() == "<div><h1>Title</h1><p>Content</p></div>"

    def test_self_closing_tag(self):
        source = '''
def br():
    return <br />
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        assert ns["br"]() == "<br />"

    def test_single_line_element(self):
        source = '''
def greet():
    return <span>Hello</span>
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        assert ns["greet"]() == "<span>Hello</span>"


class TestVariableInterpolation:
    def test_dynamic_content(self):
        source = '''
def dynamic(title, content):
    return (
        <div>
            <h1>{title}</h1>
            <p>{content}</p>
        </div>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["dynamic"]("My Title", "My Content")
        assert "<h1>My Title</h1>" in html
        assert "<p>My Content</p>" in html

    def test_escaping(self):
        source = '''
def unsafe():
    return <div>{"<script>alert('xss')</script>"}</div>
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["unsafe"]()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestForLoops:
    def test_list_items(self):
        source = '''
def list_items():
    items = ["apple", "banana", "cherry"]
    return (
        <ul>
            for item in items:
                <li>{item}</li>
        </ul>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["list_items"]()
        assert "<li>apple</li>" in html
        assert "<li>banana</li>" in html
        assert "<li>cherry</li>" in html

    def test_range_loop(self):
        source = '''
def numbers():
    return (
        <div>
            for i in range(3):
                <span>{i}</span>
        </div>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["numbers"]()
        assert "<span>0</span>" in html
        assert "<span>1</span>" in html
        assert "<span>2</span>" in html


class TestConditionals:
    def test_if_continue(self):
        source = '''
def filtered_list():
    return (
        <div>
            for i in range(10):
                if i % 2 == 0:
                    continue
                <span>Odd: {i}</span>
        </div>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["filtered_list"]()
        assert "<span>Odd: 1</span>" in html
        assert "<span>Odd: 3</span>" in html
        assert "<span>Odd: 0</span>" not in html

    def test_if_else(self):
        source = '''
def toggle(show):
    return (
        <div>
            if show:
                <span>Visible</span>
            else:
                <span>Hidden</span>
        </div>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        assert "<span>Visible</span>" in ns["toggle"](True)
        assert "<span>Hidden</span>" in ns["toggle"](False)


class TestFStrings:
    def test_fstring_interpolation(self):
        source = '''
def formatted(name, age):
    return (
        <div>
            <p>{f"Hello {name}, you are {age} years old"}</p>
        </div>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["formatted"]("Alice", 30)
        assert "Hello Alice, you are 30 years old" in html


class TestNestedComponents:
    def test_component_function_call(self):
        source = '''
def greeting(name):
    return <span>Hello, {name}!</span>

def page():
    return (
        <div>
            {greeting("World")}
        </div>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["page"]()
        assert "<span>Hello, World!</span>" in html

    def test_component_in_loop(self):
        source = '''
def item_card(text):
    return <li>{text}</li>

def list_page():
    items = ["a", "b", "c"]
    return (
        <ul>
            for item in items:
                {item_card(item)}
        </ul>
    )
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["list_page"]()
        assert "<li>a</li>" in html
        assert "<li>b</li>" in html
        assert "<li>c</li>" in html

    def test_function_call_not_escaped(self):
        source = '''
def html_output():
    return "<strong>bold</strong>"

def page():
    return <div>{html_output()}</div>
'''
        result = transpile(source)
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["page"]()
        assert "<strong>bold</strong>" in html
        assert "&lt;strong&gt;" not in html


class TestTypeAnnotations:
    def test_typed_function(self):
        source = '''
def typed_div(title: str, count: int) -> str:
    return (
        <div>
            <h1>{title}</h1>
            <p>Count: {count}</p>
        </div>
    )
'''
        result = transpile(source)
        # Just verify it transpiles without error and types are preserved
        assert "def typed_div(title: str, count: int) -> str:" in result
        ns = {"_escape": _escape}
        exec(result, ns)
        html = ns["typed_div"]("Test", 5)
        assert "Count: 5" in html
