from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/App.tsx"

text = TARGET.read_text()
old = "  const displayArtifacts = generated.length\n"
new = "  const displayArtifacts: GeneratedArtifact[] = generated.length\n"

if new in text:
    print("PASS: tipado de displayArtifacts ya estaba aplicado.")
elif old in text:
    TARGET.write_text(text.replace(old, new, 1))
    print("PASS: tipado de Package & Versiones corregido.")
else:
    raise SystemExit("Pattern not found: displayArtifacts")
