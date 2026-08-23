from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/App.tsx"
CSS = ROOT / "src/styles.css"
PREVIEW = ROOT / "preview/governance-dashboard"
PUBLIC_GOV = ROOT / "public/governance-dashboard"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"Pattern not found in {path}:\n{old[:220]}")
    path.write_text(text.replace(old, new, 1))


if not PREVIEW.exists():
    raise SystemExit(f"Governance preview source not found: {PREVIEW}")

# Publish the already validated governance dashboard as a static asset of the
# same production frontend. Vite copies /public to /dist unchanged.
PUBLIC_GOV.parent.mkdir(parents=True, exist_ok=True)
if PUBLIC_GOV.exists():
    shutil.rmtree(PUBLIC_GOV)
shutil.copytree(PREVIEW, PUBLIC_GOV)

replace_once(
    APP,
    """        {workflow.activeStep === 'governance' && (\n          <GovernanceStep />\n        )}\n""",
    """        {workflow.activeStep === 'governance' && (\n          <GovernanceIntegratedStep />\n        )}\n""",
)

marker = "\nfunction GovernanceStep() {\n"
component = r'''
function GovernanceIntegratedStep() {
  const [frameKey, setFrameKey] = useState(0);
  const governancePath = '/governance-dashboard/index.html#view/overview';

  return (
    <section className="governanceIntegratedShell">
      <div className="governanceIntegratedHeader">
        <div>
          <span className="resultEyebrow">GOBIERNO DATAOPS · PRODUCCIÓN</span>
          <h2>Control Center de Gobierno</h2>
          <p>
            Dashboard unificado de AgentOps, FinOps IA, calidad runtime, agentes,
            ejecuciones, salud, artefactos y alertas usando evidencia productiva.
          </p>
        </div>
        <div className="actions">
          <button onClick={() => setFrameKey((value) => value + 1)}>Actualizar dashboard</button>
          <a className="primary governanceOpenButton" href={governancePath} target="_blank" rel="noreferrer">
            Abrir vista completa
          </a>
        </div>
      </div>
      <div className="governanceIntegratedFrameWrap">
        <iframe
          key={frameKey}
          className="governanceIntegratedFrame"
          title="Gobierno DataOps Business Rules Silver"
          src={governancePath}
        />
      </div>
      <small className="governanceIntegratedNote">
        La vista está empaquetada dentro del mismo frontend productivo; no depende del servicio preview separado.
      </small>
    </section>
  );
}
'''

app_text = APP.read_text()
if marker not in app_text:
    raise SystemExit("GovernanceStep marker not found in src/App.tsx")
APP.write_text(app_text.replace(marker, "\n" + component + marker, 1))

css = CSS.read_text()
css_block = r'''

/* v1.1 · Governance dashboard integrated into the operational wizard */
.governanceIntegratedShell {
  display: grid;
  gap: 16px;
}

.governanceIntegratedHeader {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 22px;
  border: 1px solid var(--border-color, #dfe3eb);
  border-radius: 18px;
  background: #fff;
}

.governanceIntegratedHeader h2 {
  margin: 4px 0 8px;
}

.governanceIntegratedHeader p {
  margin: 0;
  max-width: 850px;
}

.governanceOpenButton {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}

.governanceIntegratedFrameWrap {
  overflow: hidden;
  min-height: 900px;
  border: 1px solid var(--border-color, #dfe3eb);
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 18px 48px rgba(34, 42, 68, 0.08);
}

.governanceIntegratedFrame {
  display: block;
  width: 100%;
  min-height: 1100px;
  border: 0;
  background: #fff;
}

.governanceIntegratedNote {
  color: #687083;
}

@media (max-width: 900px) {
  .governanceIntegratedHeader {
    flex-direction: column;
  }
  .governanceIntegratedFrameWrap,
  .governanceIntegratedFrame {
    min-height: 1200px;
  }
}
'''

if "v1.1 · Governance dashboard integrated" not in css:
    CSS.write_text(css + css_block)

print("P1.1 applied: validated governance dashboard embedded into Paso 7 and packaged with production frontend")
