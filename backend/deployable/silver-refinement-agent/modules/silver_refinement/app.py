from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from modules.agentops.router import router as agentops_router
from modules.governance.audit_router import router as audit_router
from modules.governance.promotion_router import router as promotion_router
from modules.governance.rollback_router import router as rollback_router
from modules.governance.router import router as governance_router
from modules.governance.summary_router import router as summary_router
from modules.intelligence.assistant_router import router as assistant_router
from modules.intelligence.context_router import router as intelligence_router
from modules.intelligence.diagnosis_router import router as diagnosis_router
from modules.intelligence.remediation_router import router as remediation_router
from modules.multi_agent.memory_router import router as memory_router
from modules.multi_agent.planning_router import router as planning_router
from modules.multi_agent.router import router as multi_agent_router
from modules.platform_availability.router import router as platform_availability_router
from modules.silver_agents.router import router as silver_agents_router
from modules.silver_execution.execution_router import router as execution_router
from modules.silver_workflow.router import router as silver_workflow_router

from .artifact_router import router as artifact_router


app = FastAPI(
    title="Silver Refinement Agent API",
    version="8.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(artifact_router)
app.include_router(silver_workflow_router)
app.include_router(execution_router)
app.include_router(silver_agents_router)
app.include_router(agentops_router)
app.include_router(governance_router)
app.include_router(promotion_router)
app.include_router(rollback_router)
app.include_router(audit_router)
app.include_router(summary_router)
app.include_router(intelligence_router)
app.include_router(diagnosis_router)
app.include_router(remediation_router)
app.include_router(assistant_router)
app.include_router(multi_agent_router)
app.include_router(planning_router)
app.include_router(memory_router)
app.include_router(platform_availability_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "module": "silver-refinement", "version": "8.2.0"}
