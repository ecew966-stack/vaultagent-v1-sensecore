from __future__ import annotations
from src.delegation.schemas import BoundSlot, EntityType, KnowledgeAtom

class UndeclaredSlotError(RuntimeError): pass
class MissingLocalEvidenceError(RuntimeError): pass

class SlotBinder:
    SLOT_TYPES = {
        "PRIVATE_PERSON_CONTEXT": {EntityType.PERSON},
        "PRIVATE_PROJECT_CONTEXT": {EntityType.PROJECT},
        "PRIVATE_BUDGET_CONTEXT": {EntityType.BUDGET},
        "PRIVATE_SCORE_CONTEXT": {EntityType.SCORE},
        "RECENT_ERROR_EXAMPLE": {EntityType.MISCONCEPTION, EntityType.SCORE},
        "PRIVATE_HEALTH_CONTEXT": {EntityType.HEALTH},
        "PRIVATE_ADDRESS_CONTEXT": {EntityType.ADDRESS},
    }

    def bind(self, slot_name: str, *, declared_slots: set[str],
             atoms: list[KnowledgeAtom]) -> BoundSlot:
        if slot_name not in declared_slots:
            raise UndeclaredSlotError(slot_name)
        expected = self.SLOT_TYPES.get(slot_name)
        matches = [a for a in atoms if expected is None or a.type in expected]
        if not matches:
            raise MissingLocalEvidenceError(slot_name)
        return BoundSlot(name=slot_name, atom_ids=[a.atom_id for a in matches],
                         local_values=[a.value for a in matches],
                         sources=sorted({a.source for a in matches}))
