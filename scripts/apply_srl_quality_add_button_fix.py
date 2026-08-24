from pathlib import Path

path = Path('src/App.tsx')
text = path.read_text(encoding='utf-8')

old_actions = '''          <div className="actions">\n            <button className="primary" disabled={!srlText.trim() || srlLoading} onClick={() => void validateSrlRule()}>\n              {srlLoading ? 'Validando...' : 'Validar SRL'}\n            </button>\n            <button onClick={() => setSrlText('CHECK ramo_id NOT_NULL\\nON_FAIL BLOCK_LOAD')}>Ejemplo NOT_NULL</button>\n            <button onClick={() => setSrlText('CHECK moneda IN ["PEN", "USD"]\\nON_FAIL WARN')}>Ejemplo IN</button>\n          </div>'''

new_actions = '''          <div className="actions">\n            <button className="primary" disabled={!srlText.trim() || srlLoading} onClick={() => void validateSrlRule()}>\n              {srlLoading ? 'Validando...' : 'Validar SRL'}\n            </button>\n            <button\n              className={srlPreview ? 'primary' : ''}\n              disabled={!srlPreview || srlLoading}\n              onClick={addValidatedSrlRule}\n              title={srlPreview ? 'Agregar contrato SRL validado' : 'Primero valida la regla SRL'}\n            >\n              Agregar regla SRL\n            </button>\n            <button onClick={() => setSrlText('CHECK ramo_id NOT_NULL\\nON_FAIL BLOCK_LOAD')}>Ejemplo NOT_NULL</button>\n            <button onClick={() => setSrlText('CHECK moneda IN ["PEN", "USD"]\\nON_FAIL WARN')}>Ejemplo IN</button>\n          </div>'''

if old_actions not in text:
    raise SystemExit('No se encontró el bloque de acciones SRL esperado')
text = text.replace(old_actions, new_actions, 1)

old_preview_button = '''              <div className="actions">\n                <button className="primary" onClick={addValidatedSrlRule}>Agregar regla validada</button>\n              </div>'''

if old_preview_button in text:
    text = text.replace(old_preview_button, '', 1)

path.write_text(text, encoding='utf-8')
print('SRL add button fix applied: persistent Validate -> Add rule flow')
