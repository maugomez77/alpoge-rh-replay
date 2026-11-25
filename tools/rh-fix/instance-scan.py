#!/usr/bin/env python3
"""Instance-shadowing census for a Lean tree.

Why: this repo carries ~19k file-local `attribute [-instance]` patches (10k+
files).  Each one is a single-line landmine: removing it can block a full build.
This scanner finds the underlying pattern without needing a build:

  * every `instance` declaration (class + head constructor + scope),
  * every `attribute [instance]` promotion,
  * every `attribute [-instance] X Y` line (what is switched off, where),

then groups by the instance-resolution key `(class, head)` and ranks the losers.

Two kinds of "duplicate" are reported separately:
  * concrete keys  — head is a real type constructor (`GL`, `Matrix`, `OcC`);
    these genuinely shadow each other,
  * wildcard keys  — head is a section variable (`O`, `R`, `s`); Lean keys
    these on `*`, so they do not shadow, but each goal tries all of them
    (synthesis cost, and a global instance everyone disables is still dead weight).

Usage:
  instance-scan.py --src src --out ~/.rh-fix/instance-census
  instance-scan.py --src src --changed-only origin/main --json
  instance-scan.py --src src --baseline census.json --gate

Exit codes: 0 ok, 1 gate violation, 2 usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

# A Lean identifier can start with any Unicode letter (𝓞, φ, …) or `_`.
TOKEN = re.compile(r"[^\W\d][\w'.!?]*", re.UNICODE)
INSTANCE_RE = re.compile(
    r"(?m)^\s*((?:@\[[^\]]*\]\s*)*)"
    r"((?:(?:noncomputable|private|protected|scoped|local|unsafe)\s+)*)instance\b"
)
BLOCK_RE = re.compile(r"(?m)^\s*(namespace(?:\s+([\w'.]+))?|section(?:\s+([\w'.]+))?|mutual|end(?:\s+([\w'.]+))?)\b")
DISABLE_RE = re.compile(r"attribute\s*\[-instance\]\s*([^\n]*)")
PROMOTE_RE = re.compile(r"attribute\s*\[instance\]\s*([^\n]*)")


# ---------------------------------------------------------------- tokenizing

def strip_comments(text: str) -> str:
    """Blank out comments and strings, preserving newlines and offsets."""
    out = list(text)
    i, n = 0, len(text)
    depth = 0
    while i < n:
        c = text[i]
        if depth:
            if text.startswith("/-", i):
                depth += 1
                out[i] = out[i + 1] = " "
                i += 2
            elif text.startswith("-/", i):
                depth -= 1
                out[i] = out[i + 1] = " "
                i += 2
            else:
                if c != "\n":
                    out[i] = " "
                i += 1
            continue
        if text.startswith("/-", i):
            depth = 1
            out[i] = out[i + 1] = " "
            i += 2
            continue
        if text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == '"':
            out[i] = " "
            i += 1
            while i < n:
                if text[i] == "\\":
                    out[i] = " "
                    if i + 1 < n:
                        if text[i + 1] != "\n":
                            out[i + 1] = " "
                        i += 2
                        continue
                if text[i] == '"':
                    out[i] = " "
                    i += 1
                    break
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def match_close(text: str, i: int) -> int:
    pairs = {"(": ")", "[": "]", "{": "}"}
    open_c = text[i]
    close_c = pairs[open_c]
    depth = 0
    while i < len(text):
        if text[i] == open_c:
            depth += 1
        elif text[i] == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def header_end(text: str, start: int) -> int:
    """End of an instance header: first top-level `:=` or `where`."""
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if c in "([{":
            i = match_close(text, i)
            continue
        if text.startswith(":=", i):
            return i
        if text.startswith("where", i) and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
            return i
        i += 1
    return n


def split_type(header: str) -> str:
    """Return the part after the last top-level colon of an instance header."""
    i, n = 0, len(header)
    last = -1
    while i < n:
        c = header[i]
        if c in "([{":
            i = match_close(header, i)
            continue
        if c == ":" and not header.startswith(":=", i) and not header.startswith("::", i):
            last = i
        i += 1
    return header[last + 1:].strip() if last >= 0 else ""


def binder_names(header: str, stop: int) -> set[str]:
    """Names bound by explicit/implicit/instance binders before `stop`."""
    names: set[str] = set()
    i = 0
    while i < stop:
        if header[i] in "([{":
            end = match_close(header, i)
            group = header[i + 1:end - 1]
            # first identifier of each comma-separated binder group
            depth = 0
            start = 0
            for j, ch in enumerate(group + ","):
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    seg = group[start:j].strip()
                    m = TOKEN.match(seg)
                    if m:
                        names.add(m.group(0).rsplit(".", 1)[-1])
                    start = j + 1
            i = end
            continue
        i += 1
    return names


def head_constructor(type_expr: str) -> str:
    s = type_expr.strip()
    while s and s[0] in "∀{[((":
        if s[0] == "∀":
            s = s[1:].lstrip()
            if s.startswith("(") or s.startswith("{"):
                s = s[match_close(s, 0):].lstrip()
            else:
                m = TOKEN.match(s)
                s = s[m.end():].lstrip() if m else s
            if s.startswith(","):
                s = s[1:].lstrip()
            continue
        if s[0] in "{[":
            end = match_close(s, 0)
            s = s[end:].lstrip()
            if s.startswith("→") or s.startswith("->"):
                s = s.lstrip("→-> ").lstrip()
                continue
            break
        if s[0] == "(":
            end = match_close(s, 0)
            inner = s[1:end - 1].strip()
            if TOKEN.match(inner) and re.match(r"^[^\W\d][\w'.]*\s*:", inner):
                s = s[end:].lstrip()
                continue
            s = inner
            break
    if not s:
        return ""
    if s.startswith("↥") or s.startswith("↑"):
        return "Subtype"
    m = TOKEN.match(s)
    return m.group(0) if m else ""


def key_kind(head: str, binders: set[str]) -> str:
    if not head:
        return "unknown"
    last = head.rsplit(".", 1)[-1]
    if last in binders:
        return "wildcard"
    # ASCII single letters are nearly always section variables; `𝓞` is notation
    if last.isascii() and len(last) == 1 and last.isupper():
        return "wildcard"
    if last.isascii() and last.islower() and len(last) <= 3:
        return "wildcard"
    return "concrete"


# ---------------------------------------------------------------- datatypes

@dataclass
class InstanceDecl:
    file: str
    line: int
    name: str
    full_name: str
    namespace: str
    cls: str
    head: str
    key_kind: str        # concrete | wildcard | unknown
    scope: str           # global | scoped | local | private
    type_text: str


@dataclass
class DisableLine:
    file: str
    line: int
    names: list[str]


@dataclass
class Census:
    root: str
    files: int = 0
    instances: list[InstanceDecl] = field(default_factory=list)
    disables: list[DisableLine] = field(default_factory=list)
    promoted: list[tuple[str, int, str]] = field(default_factory=list)  # file, line, name


# ---------------------------------------------------------------- scanning

def scan_file(path: Path, rel: str) -> tuple[list[InstanceDecl], list[DisableLine], list[tuple[str, int, str]]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = strip_comments(raw)
    out_i: list[InstanceDecl] = []
    out_d: list[DisableLine] = []
    promoted: list[tuple[str, int, str]] = []

    for m in DISABLE_RE.finditer(text):
        names = [t.replace("_root_.", "") for t in TOKEN.findall(m.group(1))]
        if names:
            out_d.append(DisableLine(rel, text.count("\n", 0, m.start()) + 1, names))
    for m in PROMOTE_RE.finditer(text):
        for t in TOKEN.findall(m.group(1)):
            promoted.append((rel, text.count("\n", 0, m.start()) + 1, t.replace("_root_.", "")))

    stack: list[tuple[str, str]] = []
    events: list[tuple[int, str, re.Match]] = []
    for m in BLOCK_RE.finditer(text):
        events.append((m.start(), "block", m))
    for m in INSTANCE_RE.finditer(text):
        events.append((m.start(), "instance", m))
    events.sort(key=lambda e: e[0])

    for pos, kind, m in events:
        if kind == "block":
            word = (m.group(1).split() or [""])[0]
            if word == "end":
                if stack:
                    stack.pop()
            elif word in ("namespace", "section", "mutual"):
                stack.append((word, (m.group(2) or m.group(3) or "").strip()))
            continue

        start = m.end()
        end = header_end(text, start)
        header = text[start:end]
        line = text.count("\n", 0, pos) + 1
        type_part = split_type(header)
        cls, head = "", ""
        if type_part:
            cm = TOKEN.search(type_part)
            if cm:
                cls = cm.group(0)
                head = head_constructor(type_part[cm.end():])
        scope = "global"
        for mod in ("private", "local", "scoped"):
            if re.search(rf"\b{mod}\b", m.group(2) or ""):
                scope = mod
                break
        name = ""
        rest = header.lstrip()
        if rest.startswith("("):
            rest = rest[match_close(rest, 0):].lstrip()
        nm = TOKEN.match(rest)
        if nm and nm.group(0) != "where":
            name = nm.group(0)
        ns = ".".join(n for k, n in stack if k == "namespace" and n)
        full = f"{ns}.{name}" if (ns and name) else name
        kind = key_kind(head, binder_names(header, header.rfind(":")))
        out_i.append(InstanceDecl(
            file=rel, line=line, name=name, full_name=full, namespace=ns,
            cls=cls, head=head, key_kind=kind, scope=scope,
            type_text=(cls + (" " + head if head else "")).strip()[:300],
        ))
    return out_i, out_d, promoted


def lean_files(root: Path, changed_only: str | None) -> list[Path]:
    if changed_only:
        try:
            out = subprocess.run(
                ["git", "diff", "--name-only", changed_only, "--", "."],
                cwd=root, capture_output=True, text=True, check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"error: git diff failed: {e}", file=sys.stderr)
            sys.exit(2)
        return [root / p for p in out.splitlines() if p.endswith(".lean") and (root / p).is_file()]
    return sorted(root.rglob("*.lean"))


# ---------------------------------------------------------------- reporting

def last_component(name: str) -> str:
    return name.replace("_root_.", "").rsplit(".", 1)[-1]


def matches(disabled: str, provider: InstanceDecl) -> bool:
    d = disabled.replace("_root_.", "")
    p = provider.full_name.replace("_root_.", "")
    if not p:
        return False
    if p == d or p.endswith("." + d) or d.endswith("." + p):
        return True
    return last_component(d) == last_component(p)


def build_report(c: Census) -> tuple[str, dict]:
    providers: dict[tuple[str, str], list[InstanceDecl]] = defaultdict(list)
    for d in c.instances:
        if d.scope == "global" and d.cls and d.head:
            providers[(d.cls, d.head)].append(d)

    disabled_by: dict[str, set[str]] = defaultdict(set)
    for dl in c.disables:
        for nm in dl.names:
            disabled_by[nm].add(dl.file)

    def disabler_files_for(decls: list[InstanceDecl]) -> set[str]:
        files: set[str] = set()
        for p in decls:
            for nm, fs in disabled_by.items():
                if matches(nm, p):
                    files |= fs
        return files

    declared = {d.full_name.replace("_root_.", "") for d in c.instances if d.full_name}
    declared |= {name.replace("_root_.", "") for _, _, name in c.promoted}

    unresolved = []
    for nm, fs in disabled_by.items():
        d = nm.replace("_root_.", "")
        if not any(d == x or x.endswith("." + d) or d.endswith("." + x) or last_component(d) == last_component(x)
                   for x in declared):
            unresolved.append({"name": nm, "files": len(fs)})

    groups = []
    for (cls, head), decls in providers.items():
        files = disabler_files_for(decls)
        kinds = Counter(d.key_kind for d in decls)
        groups.append({
            "class": cls, "head": head,
            "kind": "wildcard" if kinds["wildcard"] >= kinds["concrete"] else "concrete",
            "providers": len(decls), "disabler_files": len(files),
            "names": [f"{d.full_name or d.name} ({d.file}:{d.line})" for d in decls],
            "score": len(decls) * max(len(files), 1),
        })
    groups.sort(key=lambda g: (-g["disabler_files"], -g["providers"]))
    concrete = [g for g in groups if g["kind"] == "concrete" and g["providers"] >= 2]
    wildcard = [g for g in groups if g["kind"] == "wildcard" and g["providers"] >= 2]

    removable = []
    for (cls, head), decls in providers.items():
        if len(decls) != 1:
            continue
        n = len(disabler_files_for(decls))
        if n:
            removable.append({
                "class": cls, "head": head, "kind": decls[0].key_kind,
                "disabler_files": n, "name": decls[0].full_name or decls[0].name,
                "file": decls[0].file, "line": decls[0].line,
            })
    removable.sort(key=lambda x: -x["disabler_files"])

    top_disabled = sorted(
        ({"name": nm, "files": len(fs)} for nm, fs in disabled_by.items()),
        key=lambda x: -x["files"],
    )
    scopes = Counter(d.scope for d in c.instances)
    kinds = Counter(d.key_kind for d in c.instances if d.cls)
    heads = Counter(d.head for d in c.instances if d.head)
    classes = Counter(d.cls for d in c.instances if d.cls)

    data = {
        "root": c.root, "files": c.files,
        "instances": len(c.instances), "scopes": dict(scopes), "key_kinds": dict(kinds),
        "promoted_instance_attributes": len(c.promoted),
        "disable_lines": len(c.disables),
        "disabled_names": len(disabled_by),
        "top_groups": groups[:60],
        "concrete_groups": concrete[:40],
        "wildcard_groups": wildcard[:40],
        "removable_single_provider": removable[:60],
        "unresolved_disables": sorted(unresolved, key=lambda x: -x["files"])[:60],
        "top_disabled": top_disabled[:60],
        "top_heads": heads.most_common(30),
        "top_classes": classes.most_common(30),
        "instance_decls": [asdict(d) for d in c.instances],
        "disables": [asdict(d) for d in c.disables],
        "promoted": [{"file": f, "line": l, "name": n} for f, l, n in c.promoted],
    }

    L = []
    L.append(f"# Instance-shadow census — `{c.root}`\n")
    L.append(f"- files: **{c.files}**")
    L.append(f"- instance declarations: **{len(c.instances)}**  ({', '.join(f'{k}={v}' for k, v in scopes.items())})")
    L.append(f"- promoted by `attribute [instance]`: **{len(c.promoted)}**")
    L.append(f"- `attribute [-instance]` lines: **{len(c.disables)}** in **{len({d.file for d in c.disables})}** files")
    L.append(f"- distinct disabled instance names: **{len(disabled_by)}**")
    L.append(f"- key kinds: {', '.join(f'{k}={v}' for k, v in kinds.items())}\n")

    L.append("## Concrete-key shadows (true conflicts)\n")
    L.append("| class | head | providers | disabling files | score |")
    L.append("|---|---|---:|---:|---:|")
    for g in concrete[:25]:
        L.append(f"| `{g['class']}` | `{g['head']}` | {g['providers']} | {g['disabler_files']} | {g['score']} |")

    L.append("\n## Wildcard-key groups (synthesis cost, not shadowing)\n")
    L.append("| class | head | providers | disabling files |")
    L.append("|---|---|---:|---:|")
    for g in wildcard[:20]:
        L.append(f"| `{g['class']}` | `{g['head']}` | {g['providers']} | {g['disabler_files']} |")

    L.append("\n## Most-disabled instance names\n")
    L.append("| instance | files disabling it |")
    L.append("|---|---:|")
    for d in top_disabled[:25]:
        L.append(f"| `{d['name']}` | {d['files']} |")

    L.append("\n## Concrete-key duplicate detail\n")
    for g in concrete[:15]:
        L.append(f"- **`{g['class']} {g['head']}`** — {g['providers']} providers, {g['disabler_files']} disabling files")
        for n in g["names"][:10]:
            L.append(f"  - `{n}`")

    if removable:
        L.append("\n## Removal candidates (single provider, still disabled somewhere)\n")
        L.append("| instance | class :: head | kind | disabling files | declared at |")
        L.append("|---|---|---|---:|---|")
        for r in removable[:25]:
            L.append(f"| `{r['name']}` | `{r['class']} :: {r['head']}` | {r['kind']} | {r['disabler_files']} | `{r['file']}:{r['line']}` |")
    if unresolved:
        L.append("\n## Disabled names with no declaration (dead patches)\n")
        for u in sorted(unresolved, key=lambda x: -x["files"])[:20]:
            L.append(f"- `{u['name']}` — {u['files']} files")
    L.append("")
    return "\n".join(L), data


def gate(c: Census, baseline_path: Path) -> int:
    base = json.loads(baseline_path.read_text())
    old = {(d["name"], d["file"]) for d in base.get("instance_decls", []) if d.get("scope") == "global"}
    new = [(d.name, d.file, d.line) for d in c.instances if d.scope == "global"]
    added = [x for x in new if (x[0], x[1]) not in old]
    if added:
        print(f"gate: {len(added)} new global instance(s):", file=sys.stderr)
        for name, f, line in added[:30]:
            print(f"  {f}:{line} {name}", file=sys.stderr)
        return 1
    print("gate: no new global instances", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="src", help="source root (default: src)")
    ap.add_argument("--out", default=None, help="output prefix (writes .md and .json)")
    ap.add_argument("--json", action="store_true", help="print JSON to stdout")
    ap.add_argument("--changed-only", metavar="BASE", default=None, help="only files changed since BASE")
    ap.add_argument("--baseline", metavar="JSON", default=None, help="census JSON to gate against")
    ap.add_argument("--gate", action="store_true", help="fail on new global instances vs --baseline")
    args = ap.parse_args()

    root = Path(args.src)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    c = Census(root=str(root))
    files = lean_files(root, args.changed_only)
    c.files = len(files)
    for p in files:
        rel = str(p.relative_to(root.parent)) if root.name != "." else str(p)
        try:
            insts, dis, prom = scan_file(p, rel)
        except OSError as e:
            print(f"warn: {p}: {e}", file=sys.stderr)
            continue
        c.instances.extend(insts)
        c.disables.extend(dis)
        c.promoted.extend(prom)

    md, data = build_report(c)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".md").write_text(md, encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"wrote {out.with_suffix('.md')} and {out.with_suffix('.json')}")

    if args.json:
        print(json.dumps(data, indent=1))
    elif not args.out:
        print(md)

    if args.gate:
        if not args.baseline:
            print("error: --gate requires --baseline", file=sys.stderr)
            return 2
        return gate(c, Path(args.baseline))
    return 0


if __name__ == "__main__":
    sys.exit(main())
