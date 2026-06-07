import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_project import check_environment_gate


class EnvironmentGateTests(unittest.TestCase):
    def test_reads_current_gate_state_file(self):
        with tempfile.TemporaryDirectory() as temp:
            workdir = Path(temp)
            analysis = workdir / "analysis"
            analysis.mkdir()
            (workdir / "环境检查.json").write_text('{"requires_user_input": true}', encoding="utf-8")
            (workdir / "门禁状态.json").write_text(
                json.dumps({"environment": {"confirmed": True}}, ensure_ascii=False),
                encoding="utf-8",
            )
            check_environment_gate(analysis / "project.json")

    def test_blocks_when_environment_is_unconfirmed(self):
        with tempfile.TemporaryDirectory() as temp:
            workdir = Path(temp)
            analysis = workdir / "analysis"
            analysis.mkdir()
            (workdir / "环境检查.json").write_text('{"requires_user_input": true}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                check_environment_gate(analysis / "project.json")


if __name__ == "__main__":
    unittest.main()
