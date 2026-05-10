"""Core transpiler: converts .pyx files to .py files."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# JSX AST
# ---------------------------------------------------------------------------

@dataclass
class JsxNode:
    pass


@dataclass
class Element(JsxNode):
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[JsxNode] = field(default_factory=list)
    self_closing: bool = False


@dataclass
class Text(JsxNode):
    content: str


@dataclass
class Expression(JsxNode):
    code: str


@dataclass
class ForLoop(JsxNode):
    var: str
    iterable: str
    children: list[JsxNode] = field(default_factory=list)


@dataclass
class IfStmt(JsxNode):
    condition: str
    children: list[JsxNode] = field(default_factory=list)
    else_children: list[JsxNode] = field(default_factory=list)


@dataclass
class ContinueStmt(JsxNode):
    pass


@dataclass
class BreakStmt(JsxNode):
    pass


@dataclass
class ComponentCall(JsxNode):
    """A naked function call inside JSX: greeting('World')"""
    code: str


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class JsxTokenizer:
    """Tokenize a raw JSX source block into tag/expression/text tokens."""

    def __init__(self, source: str, base_indent: int = 0):
        self.source = source
        self.pos = 0
        self.base_indent = base_indent
        self.tokens: list[dict[str, Any]] = []

    def peek(self, n: int = 1) -> str:
        return self.source[self.pos : self.pos + n]

    def advance(self, n: int = 1) -> None:
        self.pos += n

    def at_end(self) -> bool:
        return self.pos >= len(self.source)

    def skip_whitespace(self) -> None:
        while not self.at_end() and self.peek() in " \t\n\r":
            self.advance()

    def read_string(self) -> str:
        """Read a double or single quoted string."""
        quote = self.peek()
        self.advance()
        result = []
        while not self.at_end():
            ch = self.peek()
            if ch == "\\":
                self.advance()
                if not self.at_end():
                    result.append(self.peek())
                    self.advance()
            elif ch == quote:
                self.advance()
                break
            else:
                result.append(ch)
                self.advance()
        return "".join(result)

    def read_until(self, stop_chars: str) -> str:
        result = []
        while not self.at_end() and self.peek() not in stop_chars:
            result.append(self.peek())
            self.advance()
        return "".join(result)

    def read_tag_name(self) -> str:
        result = []
        while not self.at_end():
            ch = self.peek()
            if ch.isalnum() or ch in "-_:":
                result.append(ch)
                self.advance()
            else:
                break
        return "".join(result)

    def tokenize(self) -> list[dict[str, Any]]:
        while not self.at_end():
            self.skip_whitespace()
            if self.at_end():
                break

            if self.peek(2) == "</":
                # Closing tag
                self.advance(2)
                tag = self.read_tag_name()
                self.skip_whitespace()
                if not self.at_end() and self.peek() == ">":
                    self.advance()
                self.tokens.append({"type": "close_tag", "tag": tag})

            elif self.peek() == "<":
                if self.peek(2) == "<!":
                    # HTML declaration (e.g. <!DOCTYPE html>) — emit literally
                    decl = self.read_until(">")
                    tail = ""
                    if not self.at_end() and self.peek() == ">":
                        self.advance()
                        tail = ">"
                    self.tokens.append({"type": "text", "text": decl + tail})
                    continue
                # Opening or self-closing tag
                self.advance()
                tag = self.read_tag_name()
                attrs: dict[str, str] = {}
                self.skip_whitespace()

                # Read attributes
                while not self.at_end() and self.peek() not in "/>":
                    attr_name = self.read_until("= />\t\n\r")
                    attr_name = attr_name.strip()
                    if not attr_name:
                        self.skip_whitespace()
                        if self.at_end() or self.peek() in "/>":
                            break
                        continue
                    self.skip_whitespace()
                    if not self.at_end() and self.peek() == "=":
                        self.advance()
                        self.skip_whitespace()
                        if not self.at_end() and self.peek() in '"\'':
                            attr_value = self.read_string()
                        elif not self.at_end() and self.peek() == "{":
                            self.advance()
                            expr = self.read_expr()
                            attr_value = f"{{{expr}}}"
                        else:
                            attr_value = self.read_until(" />\t\n\r")
                        attrs[attr_name] = attr_value
                    else:
                        attrs[attr_name] = ""
                    self.skip_whitespace()

                self.skip_whitespace()
                if not self.at_end() and self.peek(2) == "/>":
                    self.advance(2)
                    self.tokens.append({"type": "self_close", "tag": tag, "attrs": attrs})
                elif not self.at_end() and self.peek() == ">":
                    self.advance()
                    self.tokens.append({"type": "open_tag", "tag": tag, "attrs": attrs})
                else:
                    # Malformed, skip
                    pass

            elif self.peek() == "{":
                # Expression
                self.advance()
                expr = self.read_expr()
                self.tokens.append({"type": "expr", "code": expr})

            else:
                # Text
                text = self.read_until("<{\n\r")
                if text:
                    self.tokens.append({"type": "text", "text": text})

        return self.tokens

    def read_expr(self) -> str:
        """Read a Python expression inside braces, handling nested braces."""
        depth = 1
        result = []
        in_string = False
        string_quote = ""

        while not self.at_end():
            ch = self.peek()
            if ch == "\\" and in_string:
                result.append(ch)
                self.advance()
                if not self.at_end():
                    result.append(self.peek())
                    self.advance()
                continue

            if not in_string and ch in '"\'':
                in_string = True
                string_quote = ch
                result.append(ch)
                self.advance()
                continue

            if in_string and ch == string_quote:
                in_string = False
                string_quote = ""
                result.append(ch)
                self.advance()
                continue

            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        self.advance()
                        break

            result.append(ch)
            self.advance()

        return "".join(result)


# ---------------------------------------------------------------------------
# JSX Parser (line-oriented for statement support)
# ---------------------------------------------------------------------------

class JsxParser:
    """Parse a JSX block that may contain Python statements (for, if)."""

    def __init__(self, lines: list[str], base_indent: int):
        self.lines = lines
        self.base_indent = base_indent
        self.pos = 0

    def at_end(self) -> bool:
        return self.pos >= len(self.lines)

    def current_line(self) -> str:
        if self.at_end():
            return ""
        return self.lines[self.pos]

    def current_indent(self) -> int:
        line = self.current_line()
        stripped = line.lstrip()
        if not stripped:
            return float("inf")  # type: ignore[return-value]
        return len(line) - len(stripped)

    def peek_stripped(self) -> str:
        return self.current_line().strip()

    def advance(self) -> None:
        self.pos += 1

    COMPONENT_RE = re.compile(r"^([A-Z][a-zA-Z0-9_]*)\b(.*)$")

    def parse(self) -> list[JsxNode]:
        nodes: list[JsxNode] = []
        while not self.at_end():
            indent = self.current_indent()
            # Stop when we dedent below base_indent (but base_indent itself is valid for the first line)
            if indent < self.base_indent and self.current_line().strip():
                break

            stripped = self.peek_stripped()

            if stripped.startswith("for ") and stripped.endswith(":"):
                nodes.append(self.parse_for())
            elif stripped.startswith("if ") and stripped.endswith(":"):
                nodes.append(self.parse_if())
            elif stripped == "continue":
                nodes.append(ContinueStmt())
                self.advance()
            elif stripped == "break":
                nodes.append(BreakStmt())
                self.advance()
            elif stripped.startswith("</"):
                # Closing tag - just skip it (it was handled by the matching opener)
                self.advance()
            elif stripped.startswith("<!"):
                # HTML declaration (e.g. <!DOCTYPE html>) — emit literally
                nodes.extend(self.parse_text_line())
                self.advance()
            elif stripped.startswith("<"):
                nodes.append(self.parse_element())
            elif self._is_component_call(stripped):
                nodes.append(self.parse_component_call())
            elif stripped:
                # Text line - could contain {expr}
                nodes.extend(self.parse_text_line())
                self.advance()
            else:
                # Empty line, skip
                self.advance()

        return nodes

    # Matches a function call at the start of a line: identifier(...)
    FUNC_CALL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*\(")

    def _is_component_call(self, line: str) -> bool:
        """Check if a line is a naked function call (identifier followed by '(')."""
        return bool(self.FUNC_CALL_RE.match(line))

    def parse_for(self) -> ForLoop:
        line = self.peek_stripped()
        self.advance()
        # Parse: for var in iterable:
        match = re.match(r"for\s+(.+?)\s+in\s+(.+):", line)
        if not match:
            raise SyntaxError(f"Invalid for loop: {line}")
        var = match.group(1).strip()
        iterable = match.group(2).strip()

        # Parse children at greater indent
        child_indent = self.current_indent()
        children = self.parse_children_until_dedent(child_indent)
        return ForLoop(var=var, iterable=iterable, children=children)

    def parse_if(self) -> IfStmt:
        line = self.peek_stripped()
        self.advance()
        condition = line[3:-1].strip()  # Remove "if " and ":"

        child_indent = self.current_indent()
        children = self.parse_children_until_dedent(child_indent)

        else_children: list[JsxNode] = []
        if not self.at_end():
            stripped = self.peek_stripped()
            if stripped.startswith("else:") or stripped == "else":
                self.advance()
                else_indent = self.current_indent()
                else_children = self.parse_children_until_dedent(else_indent)

        return IfStmt(condition=condition, children=children, else_children=else_children)

    def parse_component_call(self) -> ComponentCall:
        """Parse a naked function call: greeting('World')"""
        line = self.peek_stripped()
        self.advance()
        return ComponentCall(code=line)

    def parse_children_until_dedent(self, min_indent: int) -> list[JsxNode]:
        children: list[JsxNode] = []
        while not self.at_end():
            indent = self.current_indent()
            stripped = self.peek_stripped()
            if not stripped:
                self.advance()
                continue
            if indent < min_indent:
                break

            # Temporarily set base_indent to min_indent for parsing
            parser = JsxParser(self.lines[self.pos :], min_indent)
            nodes = parser.parse()
            children.extend(nodes)
            self.pos += parser.pos

        return children

    def parse_element(self) -> JsxNode:
        line = self.current_line().strip()
        self.advance()

        # Use the tokenizer on just this line first, for single-line elements
        tokenizer = JsxTokenizer(line)
        tokens = tokenizer.tokenize()

        if len(tokens) == 1 and tokens[0]["type"] == "self_close":
            t = tokens[0]
            return Element(tag=t["tag"], attrs=t.get("attrs", {}), children=[], self_closing=True)

        # Check if it's a single-line <tag>...</tag>
        if len(tokens) >= 2 and tokens[0]["type"] == "open_tag":
            open_tag = tokens[0]
            # Find matching close tag
            depth = 1
            close_idx = None
            for i, tok in enumerate(tokens[1:], 1):
                if tok["type"] == "open_tag":
                    depth += 1
                elif tok["type"] == "close_tag":
                    depth -= 1
                    if depth == 0:
                        close_idx = i
                        break

            if close_idx is not None and close_idx == len(tokens) - 1:
                # Single line element
                inner_tokens = tokens[1:close_idx]
                children = self.tokens_to_nodes(inner_tokens)
                return Element(
                    tag=open_tag["tag"], attrs=open_tag.get("attrs", {}), children=children
                )

        # Multi-line element
        # First token must be open_tag
        if tokens[0]["type"] != "open_tag":
            raise SyntaxError(f"Expected opening tag, got: {line}")

        open_tag = tokens[0]
        tag_name = open_tag["tag"]
        attrs = open_tag.get("attrs", {})

        # If there are trailing tokens on the same line after open_tag, collect them
        trailing_tokens = tokens[1:]
        trailing_nodes = self.tokens_to_nodes(trailing_tokens)

        # Parse children until closing tag
        child_indent = self.current_indent()
        children: list[JsxNode] = []
        children.extend(trailing_nodes)

        # Collect all subsequent lines that are indented more than base
        # until we hit </tag>
        all_child_lines: list[str] = []
        while not self.at_end():
            current = self.current_line()
            stripped = current.strip()
            if stripped == f"</{tag_name}>":
                self.advance()
                break
            all_child_lines.append(current)
            self.advance()

        if all_child_lines:
            child_parser = JsxParser(all_child_lines, self.base_indent)
            children.extend(child_parser.parse())

        return Element(tag=tag_name, attrs=attrs, children=children)

    def parse_text_line(self) -> list[JsxNode]:
        line = self.current_line().strip()
        tokenizer = JsxTokenizer(line)
        tokens = tokenizer.tokenize()
        return self.tokens_to_nodes(tokens)

    def tokens_to_nodes(self, tokens: list[dict[str, Any]]) -> list[JsxNode]:
        nodes: list[JsxNode] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            ttype = tok["type"]

            if ttype == "text":
                nodes.append(Text(content=tok["text"]))
                i += 1
            elif ttype == "expr":
                nodes.append(Expression(code=tok["code"]))
                i += 1
            elif ttype == "open_tag":
                # Find matching close tag
                tag = tok["tag"]
                depth = 1
                j = i + 1
                while j < len(tokens):
                    if tokens[j]["type"] == "open_tag":
                        depth += 1
                    elif tokens[j]["type"] == "close_tag":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1

                if j < len(tokens) and tokens[j]["type"] == "close_tag":
                    inner = tokens[i + 1 : j]
                    children = self.tokens_to_nodes(inner)
                    nodes.append(
                        Element(tag=tag, attrs=tok.get("attrs", {}), children=children)
                    )
                    i = j + 1
                else:
                    # No close tag in tokens - this shouldn't happen for single-line
                    nodes.append(
                        Element(tag=tag, attrs=tok.get("attrs", {}), children=[])
                    )
                    i += 1
            elif ttype == "self_close":
                nodes.append(Element(tag=tok["tag"], attrs=tok.get("attrs", {}), children=[], self_closing=True))
                i += 1
            else:
                i += 1

        return nodes


# ---------------------------------------------------------------------------
# Code Generator
# ---------------------------------------------------------------------------

class CodeGenerator:
    """Generate Python code from a JSX AST."""

    _tmp_counter = 0

    def __init__(self, indent_str: str = "    "):
        self.indent_str = indent_str
        self.lines: list[str] = []
        self.indent_level = 0

    def emit(self, line: str) -> None:
        self.lines.append(self.indent_str * self.indent_level + line)

    def indented(self) -> "CodeGenerator":
        gen = CodeGenerator(self.indent_str)
        gen.indent_level = self.indent_level + 1
        return gen

    def generate(self, nodes: list[JsxNode]) -> str:
        self.lines = []
        self.indent_level = 0
        self._gen_nodes(nodes)
        return "\n".join(self.lines)

    def _gen_nodes(self, nodes: list[JsxNode]) -> None:
        for node in nodes:
            self._gen_node(node)

    def _gen_node(self, node: JsxNode) -> None:
        if isinstance(node, Text):
            if node.content:
                self.emit(f"_buf.append({repr(node.content)})")
        elif isinstance(node, Expression):
            self._gen_expression(node)
        elif isinstance(node, Element):
            self._gen_element(node)
        elif isinstance(node, ComponentCall):
            self._gen_component_call(node)
        elif isinstance(node, ForLoop):
            self._gen_for(node)
        elif isinstance(node, IfStmt):
            self._gen_if(node)
        elif isinstance(node, ContinueStmt):
            self.emit("continue")
        elif isinstance(node, BreakStmt):
            self.emit("break")

    def _is_function_call(self, code: str) -> bool:
        """Check if the expression is a function call (contains unquoted '(')."""
        in_string = False
        string_quote = ""
        for ch in code:
            if ch == "\\" and in_string:
                continue
            if not in_string and ch in ('"', "'"):
                in_string = True
                string_quote = ch
                continue
            if in_string and ch == string_quote:
                in_string = False
                string_quote = ""
                continue
            if not in_string and ch == "(":
                return True
        return False

    def _gen_expression(self, node: Expression) -> None:
        code = node.code.strip()
        # F-strings: don't escape (they handle their own interpolation)
        if code.startswith("f") and code[1:2] in ('"', "'"):
            self.emit(f"_buf.append(str({code}))")
            return
        # Function calls: don't escape (they return HTML/SafeString)
        if self._is_function_call(code):
            self.emit(f"_buf.append(str({code}))")
            return
        # Everything else: escape for safety
        self.emit(f"_buf.append(str(_escape({code})))")

    def _gen_component_call(self, node: ComponentCall) -> None:
        """Generate code for a naked function call: greeting('World')"""
        self.emit(f"_buf.append(str({node.code}))")

    def _gen_element(self, node: Element) -> None:
        tag = node.tag
        if node.self_closing:
            if node.attrs:
                self.emit(f"_buf.append(\"<{tag}\")")
                for name, value in node.attrs.items():
                    if value.startswith("{") and value.endswith("}"):
                        expr = value[1:-1]
                        self.emit(f"_buf.append(f' {name}=\"{{_escape({expr})}}\"')")
                    else:
                        self.emit(f"_buf.append(\" {name}=\\\"{value}\\\"\")")
                self.emit(f"_buf.append(\" />\")")
            else:
                self.emit(f"_buf.append(\"<{tag} />\")")
            return

        # Build opening tag with attributes
        attrs_str = ""
        for name, value in node.attrs.items():
            if value.startswith("{") and value.endswith("}"):
                expr = value[1:-1]
                pass
            else:
                attrs_str += f' {name}="{value}"'

        if node.attrs:
            self.emit(f"_buf.append(\"<{tag}\")")
            for name, value in node.attrs.items():
                if value.startswith("{") and value.endswith("}"):
                    expr = value[1:-1]
                    self.emit(f"_buf.append(f' {name}=\"{{_escape({expr})}}\"')")
                else:
                    self.emit(f"_buf.append(\" {name}=\\\"{value}\\\"\")")
            self.emit(f"_buf.append(\">\")")
        else:
            self.emit(f"_buf.append(\"<{tag}>\")")

        self._gen_nodes(node.children)
        self.emit(f"_buf.append(\"</{tag}>\")")

    def _gen_for(self, node: ForLoop) -> None:
        self.emit(f"for {node.var} in {node.iterable}:")
        self.indent_level += 1
        self._gen_nodes(node.children)
        self.indent_level -= 1

    def _gen_if(self, node: IfStmt) -> None:
        self.emit(f"if {node.condition}:")
        self.indent_level += 1
        self._gen_nodes(node.children)
        self.indent_level -= 1
        if node.else_children:
            self.emit("else:")
            self.indent_level += 1
            self._gen_nodes(node.else_children)
            self.indent_level -= 1


# ---------------------------------------------------------------------------
# Transpiler
# ---------------------------------------------------------------------------

class Transpiler:
    """Transpile .pyx source to .py source."""

    JSX_TAG_RE = re.compile(r"<(/?)([a-zA-Z_][a-zA-Z0-9_:-]*)")

    def __init__(self, source: str):
        self.source = source
        self.lines = source.split("\n")
        self.result: list[str] = []
        self._used: set[int] = set()  # Track consumed lines

    def transpile(self) -> str:
        """Main entry point."""
        # Pre-scan to find all JSX blocks
        blocks = self._find_all_jsx_blocks()

        # Build a set of lines that are part of any JSX block
        jsx_lines: set[int] = set()
        for block in blocks:
            for j in range(block["stmt_start"], block["stmt_end"] + 1):
                jsx_lines.add(j)

        # Process each line
        i = 0
        while i < len(self.lines):
            if i not in jsx_lines:
                self.result.append(self.lines[i])
                i += 1
                continue

            # Find the block that contains this line
            block = None
            for b in blocks:
                if b["stmt_start"] <= i <= b["stmt_end"]:
                    block = b
                    break

            if block is None:
                self.result.append(self.lines[i])
                i += 1
                continue

            # Skip to end of this block
            i = block["stmt_end"] + 1

            # Find the true start of JSX content (might be before the first < tag)
            jsx_content_start = block["jsx_start"]
            for j in range(block["stmt_start"] + 1, block["jsx_start"]):
                if self.lines[j].strip():
                    jsx_content_start = j
                    break

            # Extract JSX lines and parse
            jsx_lines_list = self.lines[jsx_content_start : block["jsx_end"] + 1]
            # Strip Python prefix before '<' ONLY if we start exactly at the < line
            if jsx_content_start == block["jsx_start"] and block.get("jsx_offset", 0) > 0:
                first = jsx_lines_list[0]
                jsx_lines_list[0] = first[block["jsx_offset"] :]
            base_indent = len(jsx_lines_list[0]) - len(jsx_lines_list[0].lstrip())

            parser = JsxParser(jsx_lines_list, base_indent)
            nodes = parser.parse()

            generator = CodeGenerator()
            generated = generator.generate(nodes)

            # Emit generated code at the statement indent level
            stmt_indent = len(self.lines[block["stmt_start"]]) - len(
                self.lines[block["stmt_start"]].lstrip()
            )

            if block["type"] == "return":
                self._emit_return_block(generated, stmt_indent)
            elif block["type"] == "assignment":
                self._emit_assignment_block(block["var_name"], generated, stmt_indent)
            else:
                self._emit_expression_block(generated, stmt_indent)

        result = "\n".join(self.result)
        # Add runtime import if needed
        if "_escape" in result and "from pyx.runtime import _escape" not in result:
            result = "from pyx.runtime import _escape\n\n" + result
        return result

    def _find_all_jsx_blocks(self) -> list[dict[str, Any]]:
        """Pre-scan the entire file to find all JSX blocks."""
        blocks: list[dict[str, Any]] = []
        found_starts: set[int] = set()
        covered: set[int] = set()  # Lines already part of a block

        for i in range(len(self.lines)):
            if i in covered:
                continue

            line = self.lines[i]
            stripped = line.strip()
            if not stripped or "<" not in line:
                continue

            match = self.JSX_TAG_RE.search(line)
            if not match:
                continue

            before = line[: match.start()].rstrip()
            if not self._is_jsx_context(before):
                continue

            base_indent = len(line) - len(line.lstrip())
            jsx_end = self._find_jsx_end(i, base_indent)
            stmt_start = self._find_statement_start(i)
            stmt_end = self._find_statement_end(jsx_end, base_indent)

            if stmt_start in found_starts:
                continue
            found_starts.add(stmt_start)

            ctx_type = self._determine_context(stmt_start)
            var_name = ""
            if ctx_type == "assignment":
                var_name = self._extract_assignment_var(stmt_start)

            # Record where JSX starts on the first line (column offset of '<')
            jsx_offset = match.start()

            # Mark all lines in this statement as covered
            for j in range(stmt_start, stmt_end + 1):
                covered.add(j)

            blocks.append({
                "stmt_start": stmt_start,
                "stmt_end": stmt_end,
                "jsx_start": i,
                "jsx_end": jsx_end,
                "jsx_offset": jsx_offset,
                "type": ctx_type,
                "var_name": var_name,
            })

        return blocks

    def _find_jsx_block(self, idx: int) -> dict[str, Any] | None:
        """Find a JSX block encompassing line idx."""
        # Look at current line and a few ahead for a JSX tag
        for jsx_start in range(idx, min(len(self.lines), idx + 5)):
            line = self.lines[jsx_start]
            match = self.JSX_TAG_RE.search(line)
            if not match:
                continue

            before = line[: match.start()].rstrip()
            if not self._is_jsx_context(before):
                continue

            # Found JSX start, now find end
            base_indent = len(line) - len(line.lstrip())
            jsx_end = self._find_jsx_end(jsx_start, base_indent)

            # Now find the statement context by looking backward
            stmt_start = self._find_statement_start(jsx_start)
            stmt_end = self._find_statement_end(jsx_end, base_indent)

            ctx_type = self._determine_context(stmt_start)
            var_name = ""
            if ctx_type == "assignment":
                var_name = self._extract_assignment_var(stmt_start)

            # Record where JSX starts on the first line (column offset of '<')
            jsx_offset = match.start()

            return {
                "stmt_start": stmt_start,
                "stmt_end": stmt_end,
                "jsx_start": i,
                "jsx_end": jsx_end,
                "jsx_offset": jsx_offset,
                "type": ctx_type,
                "var_name": var_name,
            }

        return None

    def _is_jsx_context(self, before: str) -> bool:
        """Check if the text before < suggests a JSX expression context."""
        if not before:
            return True
        # After operators/delimiters that introduce expressions
        if re.search(r"[=(,\[\{:\+\-*/]\s*$", before):
            return True
        # After return/yield
        if before.rstrip().endswith(("return", "yield")):
            return True
        return False

    def _find_jsx_end(self, start_idx: int, base_indent: int) -> int:
        """Find the last line of a JSX block by tracking tag depth."""
        depth = 0

        for i in range(start_idx, len(self.lines)):
            line = self.lines[i]
            stripped = line.strip()
            if not stripped:
                continue

            indent = len(line) - len(line.lstrip())

            # Track tag depth on this line
            line_depth = 0
            j = 0
            while j < len(line):
                if line[j] == "<":
                    if j + 1 < len(line) and line[j + 1] == "/":
                        line_depth -= 1
                        gt = line.find(">", j)
                        if gt == -1:
                            break
                        j = gt + 1
                    elif j + 1 < len(line) and line[j + 1] == "!":
                        j += 1
                    else:
                        gt = line.find(">", j)
                        if gt != -1 and line[gt - 1] == "/":
                            pass  # Self-closing
                        elif gt != -1:
                            line_depth += 1
                        j = gt + 1 if gt != -1 else j + 1
                else:
                    j += 1

            depth += line_depth

            # If we're back at base indent and depth is closed, we're done
            if i > start_idx and indent <= base_indent and depth <= 0:
                if stripped.startswith(")") or stripped.startswith("]") or stripped.startswith("}"):
                    return i
                if not stripped.startswith("<") and not stripped.startswith("for ") and not stripped.startswith("if "):
                    return i - 1
                if depth <= 0:
                    return i

        return len(self.lines) - 1

    def _find_statement_start(self, jsx_start: int) -> int:
        """Find the line where the enclosing statement starts (return, var =, etc.)."""
        base_indent = len(self.lines[jsx_start]) - len(self.lines[jsx_start].lstrip())

        for i in range(jsx_start, max(-1, jsx_start - 10), -1):
            line = self.lines[i]
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())

            # Statement start is at same indent as JSX or less, and looks like a statement
            if indent <= base_indent:
                if stripped.startswith("return") or stripped.startswith("yield"):
                    return i
                if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*[=]", stripped):
                    return i
                if re.search(r"^\w+\s*:\s*\w+\s*[=]", stripped):
                    return i
                if stripped.endswith(":") and not stripped.startswith("if ") and not stripped.startswith("else:"):
                    # Could be a function def or similar - don't go further
                    if i < jsx_start:
                        return i + 1

        return jsx_start

    def _find_statement_end(self, jsx_end: int, base_indent: int) -> int:
        """Find where the enclosing statement ends (e.g. closing paren)."""
        # Look for closing ) ] } at base indent or less
        for i in range(jsx_end + 1, len(self.lines)):
            line = self.lines[i]
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent:
                if stripped.startswith(")") or stripped.startswith("]") or stripped.startswith("}"):
                    return i
                # Another statement started
                return i - 1
        return len(self.lines) - 1

    def _determine_context(self, stmt_start: int) -> str:
        """Determine if JSX is in a return, assignment, or general expression context."""
        line = self.lines[stmt_start].strip()
        if line.startswith("return") or line.startswith("yield"):
            return "return"
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*[=]", line):
            return "assignment"
        if re.search(r"^\w+\s*:\s*\w+\s*[=]", line):
            return "assignment"
        return "expression"

    def _extract_assignment_var(self, stmt_start: int) -> str:
        line = self.lines[stmt_start].strip()
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*[=]", line)
        if match:
            return match.group(1)
        match = re.search(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*\w+\s*[=]", line)
        if match:
            return match.group(1)
        return "_jsx_result"

    def _emit_return_block(self, generated: str, stmt_indent: int) -> None:
        indent = " " * stmt_indent
        self.result.append(indent + "_buf = []")
        for line in generated.split("\n"):
            if line.strip():
                self.result.append(indent + line)
        self.result.append(indent + 'return "".join(_buf)')

    def _emit_assignment_block(self, var_name: str, generated: str, stmt_indent: int) -> None:
        indent = " " * stmt_indent
        self.result.append(indent + "_buf = []")
        for line in generated.split("\n"):
            if line.strip():
                self.result.append(indent + line)
        self.result.append(indent + f'{var_name} = "".join(_buf)')

    def _emit_expression_block(self, generated: str, stmt_indent: int) -> None:
        indent = " " * stmt_indent
        self.result.append(indent + "_buf = []")
        for line in generated.split("\n"):
            if line.strip():
                self.result.append(indent + line)
        self.result.append(indent + '_jsx_expr = "".join(_buf)')


def transpile(source: str) -> str:
    """Transpile .pyx source code to .py source code."""
    transpiler = Transpiler(source)
    return transpiler.transpile()
