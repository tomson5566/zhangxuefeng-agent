"""测试 ModuleLoader 自动发现 + ModuleRegistry。"""
from backend.core.module_loader import ModuleLoader, default_registry


def test_module_loader_discovers_all():
    loaded = ModuleLoader.load_all(default_registry)
    assert 'llm' in loaded
    assert 'filter' in loaded
    assert 'mmx_search' in loaded
    assert 'skill_loader' in loaded
    assert 'nginx' in loaded
    assert 'doc_loader' in loaded
    assert 'deepagent_runner' in loaded
    assert 'data_sources' in loaded
    assert 'volunteer_plan' in loaded


def test_registry_has_expected_keys():
    ModuleLoader.load_all(default_registry)
    keys = set(default_registry.keys())
    expected = {
        'llm_factory', 'input_filter', 'llm_judge', 'mmx_search',
        'skill_loader', 'doc_loader', 'doc_extensions',
        'nginx_generator', 'deepagent_factory', 'deepagent_stream',
        'data.make_loader', 'data.福建', 'data.北京', 'data.广东',
        'volunteer_plan.generate',
    }
    assert expected.issubset(keys), f"Missing: {expected - keys}"


def test_registry_get_works():
    ModuleLoader.load_all(default_registry)
    assert default_registry.get('mmx_search') is not None
    assert default_registry.get('not_exists') is None
