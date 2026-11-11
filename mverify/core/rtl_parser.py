"""Lightweight structural Verilog/SystemVerilog parser; not a full HDL frontend."""
from pathlib import Path
import re

IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
MODULE_RE = re.compile(rf"\bmodule\s+(?:(?:automatic|static)\s+)?(?P<name>{IDENT})\b")
ENDMODULE_RE = re.compile(r"\bendmodule\b")
DIRECTION_RE = re.compile(r"\b(input|output|inout)\b")


def _remove_comments(text):
    out, i, state = [], 0, "code"
    while i < len(text):
        if state == "code":
            if text.startswith("//", i):
                out.extend("  "); i += 2; state = "line"; continue
            if text.startswith("/*", i):
                out.extend("  "); i += 2; state = "block"; continue
            if text[i] == '"':
                out.append(text[i]); i += 1; state = "string"; continue
            out.append(text[i]); i += 1
        elif state == "line":
            if text[i] == "\n": out.append("\n"); state = "code"
            else: out.append(" ")
            i += 1
        elif state == "block":
            if text.startswith("*/", i):
                out.extend("  "); i += 2; state = "code"
            else:
                out.append("\n" if text[i] == "\n" else " "); i += 1
        else:
            out.append(text[i])
            if text[i] == "\\" and i + 1 < len(text):
                out.append(text[i+1]); i += 2; continue
            if text[i] == '"': state = "code"
            i += 1
    return "".join(out)


def _matching(text, start, op="(", cl=")"):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == op: depth += 1
        elif text[i] == cl:
            depth -= 1
            if depth == 0: return i
    return -1


def _split_top(text, delimiter=","):
    result, start = [], 0
    p = b = c = 0
    for i, ch in enumerate(text):
        if ch == "(": p += 1
        elif ch == ")": p = max(0, p-1)
        elif ch == "[": b += 1
        elif ch == "]": b = max(0, b-1)
        elif ch == "{": c += 1
        elif ch == "}": c = max(0, c-1)
        elif ch == delimiter and p == b == c == 0:
            result.append(text[start:i].strip()); start = i+1
    result.append(text[start:].strip())
    return [x for x in result if x]


def _port(token, inherited):
    dm = DIRECTION_RE.search(token)
    direction = dm.group(1) if dm else inherited
    if not direction: return None, inherited
    token = _split_top(token, "=")[0].strip()
    # Remove trailing unpacked dimensions, then identify final declarator name.
    token = re.sub(r"(?:\s*\[[^\]]*\])+\s*$", "", token).strip()
    ids = re.findall(IDENT, token)
    excluded = {"input","output","inout","wire","reg","logic","bit","tri","tri0",
                "tri1","uwire","var","signed","unsigned","const","integer","int",
                "byte","shortint","longint","time","struct","enum","packed"}
    ids = [x for x in ids if x not in excluded]
    if not ids: return None, direction
    wm = re.search(r"\[[^\]]+\]", token)
    return {"name": ids[-1], "direction": direction,
            "width": wm.group(0) if wm else "scalar/unspecified",
            "declaration": " ".join(token.split())}, direction


def _header(source, pos):
    i = pos
    while i < len(source) and source[i].isspace(): i += 1
    if i < len(source) and source[i] == "#":
        i += 1
        while i < len(source) and source[i].isspace(): i += 1
        if i >= len(source) or source[i] != "(":
            return None, i, False, "Malformed parameter-port list."
        end = _matching(source, i)
        if end < 0: return None, i, False, "Unbalanced parameter-port list."
        i = end + 1
        while i < len(source) and source[i].isspace(): i += 1
    if i >= len(source) or source[i] != "(":
        semi = source.find(";", i)
        return None, semi+1 if semi >= 0 else i, False, "No module port list."
    end = _matching(source, i)
    if end < 0: return None, i, False, "Unbalanced module port list."
    semi = source.find(";", end)
    if semi < 0: return source[i+1:end], end+1, True, "Missing semicolon after module header."
    return source[i+1:end], semi+1, True, None


def _parameters(source, pos):
    """Extract simple ANSI parameter declarations without evaluating expressions."""
    i=pos
    while i<len(source) and source[i].isspace(): i+=1
    if i>=len(source) or source[i]!="#": return []
    i+=1
    while i<len(source) and source[i].isspace(): i+=1
    if i>=len(source) or source[i]!="(": return []
    end=_matching(source,i)
    if end<0: return []
    result=[]; inherited_type=""
    for item in _split_top(source[i+1:end]):
        declaration=item.strip()
        if not declaration: continue
        lhs,sep,rhs=declaration.partition("=")
        ids=re.findall(IDENT,lhs)
        if not ids: continue
        name=ids[-1]
        prefix=lhs[:lhs.rfind(name)].strip()
        if prefix: inherited_type=prefix
        result.append({"name":name,"type":inherited_type or "unspecified",
                       "default":rhs.strip() if sep else None,"declaration":declaration,
                       "classification":"CONFIRMED_FROM_PARSER"})
    return result


def parse_rtl_text(text, source_name="<memory>"):
    src = _remove_comments(text)
    modules, warnings = [], []
    matches = list(MODULE_RE.finditer(src))
    for m in matches:
        name = m.group("name")
        end = ENDMODULE_RE.search(src, m.end())
        if not end:
            warnings.append(f"{source_name}: module {name} has no matching endmodule.")
            continue
        port_text, body_start, has_ports, issue = _header(src, m.end())
        ports, ansi = [], False
        if port_text is not None:
            ansi = bool(DIRECTION_RE.search(port_text))
            if ansi:
                inherited = None
                for item in _split_top(port_text):
                    p, inherited = _port(item, inherited)
                    if p: ports.append(p)
            elif port_text.strip():
                warnings.append(f"{source_name}: module {name} uses a non-ANSI port list; directions and widths are not resolved.")
                for item in _split_top(port_text):
                    ids = re.findall(IDENT, item)
                    if ids:
                        ports.append({"name": ids[-1], "direction": "unspecified",
                                      "width": "scalar/unspecified", "declaration": item})
        if issue: warnings.append(f"{source_name}: module {name}: {issue}")
        modules.append({"name": name, "ports": ports, "parameters":_parameters(src,m.end()),
                        "source_line_start":src.count("\n",0,m.start())+1,
                        "source_file": source_name,
                        "port_style": "ANSI" if ansi else ("non-ANSI/unknown" if port_text else "no-port-list"),
                        "body": src[body_start:end.start()]})
    if not modules and re.search(r"\bmodule\b", src):
        warnings.append(f"{source_name}: module keyword found, but no complete module was extracted.")
    return modules, warnings


def parse_rtl_file(path: Path):
    try: text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc: return [], [f"{path}: could not read file: {exc}"]
    return parse_rtl_text(text, str(path))
