import importlib.util
import pathlib

MODULE_PATH = pathlib.Path(__file__).resolve().parent / "assmnt_test.py"


def load_module():
    spec = importlib.util.spec_from_file_location("assmnt_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_assessment_outputs(tmp_path):
    module = load_module()
    results = [{"name": "demo", "status": "passed", "response": "engine reply"}]
    transcript = ["user: hello", "engine: engine reply"]

    output_json = tmp_path / "assmnt_test_result.json"
    output_txt = tmp_path / "assmnt_test_result.txt"

    module.write_assessment_outputs(results, transcript, output_json, output_txt)

    assert output_json.exists()
    assert output_txt.exists()
    assert "demo" in output_json.read_text()
    assert "engine reply" in output_txt.read_text()
