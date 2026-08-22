from pathlib import Path

path = Path("src/App.tsx")
text = path.read_text(encoding="utf-8")

old_variants = [
    "derivationMode: typeof column.derivation_mode === 'string' ? column.derivation_mode : undefined,",
    'derivationMode: typeof column.derivation_mode === "string" ? column.derivation_mode : undefined,',
]
new = "derivationMode: column.derivation_mode === 'DERIVED_NL' ? 'DERIVED_NL' : undefined,"

if new in text:
    print("PASS: derivationMode ya usa literal DERIVED_NL.")
else:
    for old in old_variants:
        if old in text:
            text = text.replace(old, new, 1)
            path.write_text(text, encoding="utf-8")
            print("PASS: derivationMode estrechado al literal DERIVED_NL.")
            break
    else:
        raise SystemExit("No se encontro la asignacion derivationMode esperada en src/App.tsx")

print("Frontend conserva el contrato discriminado MappingRule.derivationMode sin ampliar a string.")
