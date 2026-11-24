#!/usr/bin/env python3
"""Scan changed Lean files for `_root_.` inside selective `open ... (...)` lists.

This is the systemic consolidation-pass bug: inside `open N (...)`, an entry
`_root_.N.fibre` becomes `N._root_.N.fibre` and Lean rejects the entire open,
silently leaving every other listed name unknown.

Exit 1 if any hit is found (so preflight fails), 0 otherwise.
"""
import os, re, sys

def hits_in(path):
    try:
        s = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    out = []
    for m in re.finditer(r'(?m)^\s*open\b[^\n(]*\(', s):
        start, depth, i = m.end(), 1, m.end()
        while i < len(s) and depth > 0:
            if s[i] == '(':
                depth += 1
            elif s[i] == ')':
                depth -= 1
            i += 1
        body = s[start:i-1]
        if "_root_." in body:
            line = s[:m.start()].count("\n") + 1
            out.append((path, line))
    return out

def main(paths):
    found = []
    for p in paths:
        if p.endswith(".lean") and os.path.exists(p):
            found += hits_in(p)
    for path, line in found:
        print(f"{path}:{line}: _root_. inside a selective open")
    return 1 if found else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
