from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "src/types.ts"
text = path.read_text()
old = """  content_hash?: string | null;\n  metadata?: Record<string, unknown>;\n}"""
new = """  content_hash?: string | null;\n  is_current?: boolean;\n  metadata?: Record<string, unknown>;\n}"""
if "is_current?: boolean;" in text:
    print("PASS: GeneratedArtifact ya expone is_current opcional.")
elif old not in text:
    raise SystemExit("Pattern not found in src/types.ts for GeneratedArtifact")
else:
    path.write_text(text.replace(old, new, 1))
    print("PASS: GeneratedArtifact actualizado con is_current opcional.")
