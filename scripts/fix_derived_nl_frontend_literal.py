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
            print("PASS: derivationMode estrechado al literal DERIVED_NL.")
            break
    else:
        raise SystemExit("No se encontro la asignacion derivationMode esperada en src/App.tsx")

# TypeScript puede ensanchar literales string dentro del resultado generico de Array.map.
# Contextualizamos el resultado como MappingRule para preservar el discriminante DERIVED_NL.
function_marker = "function mappingFromRecommendation(columns: Array<Record<string, unknown>>): MappingRule[] {"
untyped_map = "  return columns.map((column) => {"
typed_map = "  return columns.map<MappingRule>((column) => {"

function_pos = text.find(function_marker)
if function_pos < 0:
    raise SystemExit("No se encontro mappingFromRecommendation en src/App.tsx")

function_tail = text[function_pos:]
if typed_map in function_tail:
    print("PASS: mappingFromRecommendation ya contextualiza Array.map como MappingRule.")
elif untyped_map in function_tail:
    function_tail = function_tail.replace(untyped_map, typed_map, 1)
    text = text[:function_pos] + function_tail
    print("PASS: Array.map contextualizado como MappingRule para evitar widening a string.")
else:
    raise SystemExit("No se encontro el Array.map esperado dentro de mappingFromRecommendation")

path.write_text(text, encoding="utf-8")
print("Frontend conserva el contrato discriminado MappingRule.derivationMode sin ampliar a string.")
