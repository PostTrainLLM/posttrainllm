import json

from run_rest_arm import json_safe


class Directory:
    def __str__(self) -> str:
        return "/tmp/example"


def test_json_safe_preserves_structure_and_stringifies_simulator_values() -> None:
    value = {"result": [{"directory": Directory(), "count": 2}]}
    converted = json_safe(value)
    assert converted == {"result": [{"directory": "/tmp/example", "count": 2}]}
    assert json.loads(json.dumps(converted)) == converted
