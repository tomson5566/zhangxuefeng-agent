from backend.core.module_loader import ModuleRegistry


def register(registry: ModuleRegistry) -> None:
    from backend.modules.volunteer_plan.generator import generate_plan
    registry.register("volunteer_plan.generate", generate_plan)