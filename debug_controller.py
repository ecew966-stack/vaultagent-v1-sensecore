from src.core.settings import Settings
from src.agent.controller import VaultAgentController
from src.delegation.schemas import KnowledgeDocument, Confidentiality, Integrity, TaskRequest

settings = Settings()
settings.prepare_paths()
controller = VaultAgentController(settings)

content = '张教授负责智能体安全项目。李工程师负责系统实现，研究方向为隐私保护。项目预算120万元。'
docs = [KnowledgeDocument(
    doc_id='defense-01-team-doc', content=content, source='internal/team.docx',
    confidentiality=Confidentiality.CONFIDENTIAL, integrity=Integrity.TRUSTED,
    allowed_purposes=['planning'], allowed_sinks=['LOCAL_MODEL', 'PROTECTED_CONTEXT_CLOUD_REASONING']
)]

task = TaskRequest(
    task_id='defense-01', user_query='为张教授的团队制定四周工作计划',
    purpose='planning', local_capability=0.2, complexity=0.9, policy_budget=0.4,
    metadata={'privacy_scope_id': 'test-01', 'domain': 'enterprise_project',
              'force_mode': 'PROTECTED_CONTEXT_CLOUD_REASONING'}
)

response = controller.run(task, docs)
print(f'Mode: {response.mode.value}')
print(f'Protection decisions: {len(response.trace.protection_decisions)}')
for pd in response.trace.protection_decisions[:5]:
    op = pd.get("operation", "?")
    eid = pd.get("external_id", "?")
    if isinstance(eid, str) and len(eid) > 30:
        eid = eid[:30]
    print(f'  type={pd.get("type","?")} op={op} ext_id={eid}')
print(f'Cloud payload entities: {len(response.trace.cloud_payload.get("entities",[]))}')
if response.trace.cloud_payload:
    for e in response.trace.cloud_payload.get("entities", [])[:3]:
        eid = e.get("id", "")
        if isinstance(eid, str) and len(eid) > 40:
            eid = eid[:40]
        print(f'  id={eid} type={e.get("type","")}')
print(f'Answer: {response.answer[:200]}')
