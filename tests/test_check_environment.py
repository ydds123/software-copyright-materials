import sys
import unittest
from unittest.mock import patch
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_environment import check_lark_user_auth, is_feishu_document_target


class FeishuDocumentTargetTests(unittest.TestCase):
    def test_accepts_feishu_document_url(self):
        self.assertTrue(is_feishu_document_target("https://example.feishu.cn/wiki/CWDqw6vMwidfGhkvOjWc2uAcnHf"))

    def test_accepts_document_token(self):
        self.assertTrue(is_feishu_document_target("CWDqw6vMwidfGhkvOjWc2uAcnHf"))

    def test_rejects_missing_or_unrelated_url(self):
        self.assertFalse(is_feishu_document_target(""))
        self.assertFalse(is_feishu_document_target("https://example.com/wiki/token"))


class LarkAuthTests(unittest.TestCase):
    @patch("check_environment.command_output")
    def test_accepts_valid_user_token(self, command_output):
        command_output.return_value = (True, '{"identity":"user","tokenStatus":"valid","userName":"Tester"}')
        self.assertEqual(check_lark_user_auth(), (True, "user token valid: Tester"))

    @patch("check_environment.command_output")
    def test_rejects_bot_only_identity(self, command_output):
        command_output.return_value = (True, '{"identity":"bot","note":"user token missing"}')
        self.assertEqual(check_lark_user_auth(), (False, "user token missing"))


if __name__ == "__main__":
    unittest.main()
