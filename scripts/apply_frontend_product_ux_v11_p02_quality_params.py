from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/App.tsx"
text = APP.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f"Pattern not found:\n{old[:220]}")
    text = text.replace(old, new, 1)


replace_once(
    """  const [criticalThreshold, setCriticalThreshold] = useState(1);\n  const [qualityNlIntent, setQualityNlIntent] = useState('');\n\n  function addManual() {\n    if (!manualColumn) return;\n    if (criticalThreshold < warningThreshold) return;\n    const ruleName = `${manualColumn}_${manualType.toLowerCase()}`;\n""",
    """  const [criticalThreshold, setCriticalThreshold] = useState(1);\n  const [qualityNlIntent, setQualityNlIntent] = useState('');\n  const [allowedValuesText, setAllowedValuesText] = useState('');\n  const [rangeMin, setRangeMin] = useState('');\n  const [rangeMax, setRangeMax] = useState('');\n  const [regexPattern, setRegexPattern] = useState('');\n\n  const selectedColumnType = String(columns.find((column) => column.name === manualColumn)?.type ?? '').toUpperCase();\n  const numericQualityTypes = new Set(['INT64', 'INTEGER', 'FLOAT64', 'FLOAT', 'NUMERIC', 'BIGNUMERIC', 'DECIMAL']);\n  const stringQualityTypes = new Set(['STRING', 'BYTES']);\n\n  function manualParameters(): Record<string, unknown> {\n    if (manualType === 'ALLOWED_VALUES') {\n      return {\n        allowed_values: allowedValuesText\n          .split(/[,\\n]/)\n          .map((value) => value.trim())\n          .filter(Boolean),\n      };\n    }\n    if (manualType === 'VALUE_RANGE') {\n      return {\n        ...(rangeMin.trim() ? { min: Number(rangeMin) } : {}),\n        ...(rangeMax.trim() ? { max: Number(rangeMax) } : {}),\n      };\n    }\n    if (manualType === 'REGEX') {\n      return { pattern: regexPattern.trim() };\n    }\n    return {};\n  }\n\n  function manualParameterError(): string | undefined {\n    if (manualType === 'ALLOWED_VALUES' && !allowedValuesText.split(/[,\\n]/).map((v) => v.trim()).filter(Boolean).length) {\n      return 'ALLOWED_VALUES requiere al menos un valor permitido.';\n    }\n    if (manualType === 'VALUE_RANGE') {\n      if (!numericQualityTypes.has(selectedColumnType)) return 'VALUE_RANGE solo admite columnas numéricas.';\n      if (!rangeMin.trim() && !rangeMax.trim()) return 'VALUE_RANGE requiere mínimo y/o máximo.';\n      if (rangeMin.trim() && rangeMax.trim() && Number(rangeMin) > Number(rangeMax)) return 'VALUE_RANGE requiere mínimo <= máximo.';\n    }\n    if (manualType === 'REGEX') {\n      if (!stringQualityTypes.has(selectedColumnType)) return 'REGEX solo admite columnas STRING/BYTES.';\n      if (!regexPattern.trim()) return 'REGEX requiere un patrón.';\n    }\n    return undefined;\n  }\n\n  const parameterError = manualParameterError();\n\n  function addManual() {\n    if (!manualColumn) return;\n    if (criticalThreshold < warningThreshold) return;\n    if (parameterError) return;\n    const ruleName = `${manualColumn}_${manualType.toLowerCase()}`;\n""",
)

replace_once(
    """      parameters: {},\n      warning_threshold: warningThreshold,\n""",
    """      parameters: manualParameters(),\n      warning_threshold: warningThreshold,\n""",
)

replace_once(
    """        <ContractSelectField label=\"Tipo de regla\" value={manualType}\n          options={['NOT_NULL', 'UNIQUE', 'ALLOWED_VALUES', 'VALUE_RANGE', 'REGEX']} onChange={setManualType} />\n""",
    """        <ContractSelectField label=\"Tipo de regla\" value={manualType}\n          options={['NOT_NULL', 'UNIQUE', 'ALLOWED_VALUES', 'VALUE_RANGE', 'REGEX']} onChange={(value) => {\n            setManualType(value);\n            if (value === 'NOT_NULL') { setManualDimension('COMPLETENESS'); setManualAction('BLOCK_LOAD'); }\n            else if (value === 'UNIQUE') { setManualDimension('UNIQUENESS'); setManualAction('BLOCK_LOAD'); }\n            else { setManualDimension('VALIDITY'); setManualAction('WARN'); }\n          }} />\n""",
)

needle = """        <label className=\"field\"><span>Critical threshold</span><input type=\"number\" min=\"0\" value={criticalThreshold}\n          onChange={(event) => setCriticalThreshold(Number(event.target.value))} /></label>\n      </div>\n      <div className=\"actions\"><button onClick={addManual}>Agregar regla manual</button></div>\n      {criticalThreshold < warningThreshold && <small className=\"riskText\">Critical threshold debe ser mayor o igual que warning.</small>}\n"""
replacement = """        <label className=\"field\"><span>Critical threshold</span><input type=\"number\" min=\"0\" value={criticalThreshold}\n          onChange={(event) => setCriticalThreshold(Number(event.target.value))} /></label>\n      </div>\n\n      {manualType === 'ALLOWED_VALUES' && (\n        <div className=\"validationBox\">\n          <strong>Parámetros · Valores permitidos</strong>\n          <label className=\"field\">\n            <span>Valores (separados por coma o una línea por valor)</span>\n            <textarea rows={3} value={allowedValuesText} onChange={(event) => setAllowedValuesText(event.target.value)}\n              placeholder=\"ACTIVO, INACTIVO, SUSPENDIDO\" />\n          </label>\n          <small>Se persistirá como parameters.allowed_values.</small>\n        </div>\n      )}\n\n      {manualType === 'VALUE_RANGE' && (\n        <div className=\"validationBox\">\n          <strong>Parámetros · Rango de valores</strong>\n          <div className=\"formGrid three\">\n            <label className=\"field\"><span>Mínimo</span><input type=\"number\" value={rangeMin}\n              onChange={(event) => setRangeMin(event.target.value)} placeholder=\"0\" /></label>\n            <label className=\"field\"><span>Máximo</span><input type=\"number\" value={rangeMax}\n              onChange={(event) => setRangeMax(event.target.value)} placeholder=\"100000\" /></label>\n            <Field label=\"Tipo columna\" value={selectedColumnType || 'N/A'} />\n          </div>\n          <small>Puedes indicar solo mínimo, solo máximo o ambos. Se persistirá como parameters.min / parameters.max.</small>\n        </div>\n      )}\n\n      {manualType === 'REGEX' && (\n        <div className=\"validationBox\">\n          <strong>Parámetros · Expresión regular</strong>\n          <label className=\"field\">\n            <span>Patrón REGEX</span>\n            <input value={regexPattern} onChange={(event) => setRegexPattern(event.target.value)}\n              placeholder=\"^[A-Z]{3}-[0-9]{6}$\" />\n          </label>\n          <small>Se persistirá como parameters.pattern. La regla solo es válida para columnas STRING/BYTES.</small>\n        </div>\n      )}\n\n      <div className=\"actions\"><button onClick={addManual} disabled={Boolean(parameterError) || criticalThreshold < warningThreshold}>Agregar regla manual</button></div>\n      {criticalThreshold < warningThreshold && <small className=\"riskText\">Critical threshold debe ser mayor o igual que warning.</small>}\n      {parameterError && <small className=\"riskText\">{parameterError}</small>}\n"""
replace_once(needle, replacement)

replace_once(
    """              <small>Gate: {rule.runtime_action} · Warning {rule.warning_threshold} · Critical {rule.critical_threshold} · Origen {rule.source}</small>\n              <button className=\"dangerText\" onClick={() => onRemoveRule(rule.rule_id)}>Quitar</button>\n""",
    """              <small>Gate: {rule.runtime_action} · Warning {rule.warning_threshold} · Critical {rule.critical_threshold} · Origen {rule.source}</small>\n              {Object.keys(rule.parameters ?? {}).length > 0 && (\n                <small>Parámetros: {JSON.stringify(rule.parameters)}</small>\n              )}\n              <button className=\"dangerText\" onClick={() => onRemoveRule(rule.rule_id)}>Quitar</button>\n""",
)

APP.write_text(text)
print('P0.2 applied: dynamic Quality Rule parameters for ALLOWED_VALUES, VALUE_RANGE and REGEX')
