from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text)


# 1) Silver workflow contract: structured transformation + multi-source + DERIVED_NL traceability.
path = "backend/deployable/silver-refinement-agent/modules/silver_workflow/models.py"
text = read(path)
old = '''class SilverMappingColumn(BaseModel):\n    name: str = Field(min_length=1, max_length=300)\n    data_type: str = Field(min_length=1, max_length=200)\n    nullable: bool = True\n    source_column: str | None = Field(default=None, max_length=300)\n    transformation: str | None = Field(default=None, max_length=8000)\n    description: str | None = Field(default=None, max_length=2000)\n\n    @model_validator(mode="after")\n    def validate_mapping_source(self) -> "SilverMappingColumn":\n        if not self.source_column and not self.transformation:\n            raise ValueError("Cada columna Silver debe indicar source_column o transformation")\n        return self\n'''
new = '''class SilverMappingColumn(BaseModel):\n    name: str = Field(min_length=1, max_length=300)\n    data_type: str = Field(min_length=1, max_length=200)\n    nullable: bool = True\n    source_column: str | None = Field(default=None, max_length=300)\n    source_columns: list[str] = Field(default_factory=list)\n    transformation: dict[str, Any] | str | None = None\n    derivation_mode: str | None = Field(default=None, max_length=100)\n    natural_rule: str | None = Field(default=None, max_length=4000)\n    description: str | None = Field(default=None, max_length=2000)\n\n    @field_validator("source_columns")\n    @classmethod\n    def normalize_mapping_sources(cls, values: list[str]) -> list[str]:\n        normalized: list[str] = []\n        for raw_value in values:\n            value = raw_value.strip()\n            if not value:\n                raise ValueError("source_columns no puede contener valores vacíos")\n            if value not in normalized:\n                normalized.append(value)\n        return normalized\n\n    @model_validator(mode="after")\n    def validate_mapping_source(self) -> "SilverMappingColumn":\n        if not self.source_column and not self.source_columns and not self.transformation:\n            raise ValueError("Cada columna Silver debe indicar source_column, source_columns o transformation")\n        if self.derivation_mode == "DERIVED_NL" and not self.natural_rule:\n            raise ValueError("DERIVED_NL requiere natural_rule para trazabilidad")\n        return self\n'''
if old in text:
    text = text.replace(old, new, 1)
elif "source_columns: list[str] = Field(default_factory=list)" not in text:
    raise SystemExit("No se encontró el contrato SilverMappingColumn esperado")
write(path, text)

# 2) Frontend literal type: preserve DERIVED_NL as discriminated literal.
path = "src/App.tsx"
text = read(path)
old = "derivationMode: typeof column.derivation_mode === 'string' ? column.derivation_mode : undefined,"
new = "derivationMode: column.derivation_mode === 'DERIVED_NL' ? 'DERIVED_NL' : undefined,"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("No se encontró derivationMode en mappingFromRecommendation")
write(path, text)

print("PASS: contrato DERIVED_NL saneado.")
print("SilverMappingColumn acepta transformación estructurada/multi-source y frontend conserva el literal DERIVED_NL.")
