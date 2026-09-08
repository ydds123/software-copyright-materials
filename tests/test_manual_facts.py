# -*- coding: utf-8 -*-
"""verify_manual_facts 测试：枚举漂移、一致、字段表静默、公式清单。"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from verify_manual_facts import extract_manual_enums, run

SRC_ENUM = '''package x;
public enum TaskStatusEnum {
    UNCLAIMED("1", "待认领"),
    TO_BE("2", "待巡检"),
    INSPECTION("3", "巡检中"),
    OVERDUE_A("4", "逾期待检"),
    OVERDUE("5", "巡检超时"),
    DONE("6", "已完成"),
    UNCHECKED("7", "未检"),
    MISSED("8", "漏检"),
    RECHECK("9", "已完成（补检）"),
    UNCLAIMED_RECHECK("10", "未认领");
    private final String code;
    private final String description;
    TaskStatusEnum(String code, String description) {}
}
'''


def mk_src(tmp: Path) -> Path:
    d = tmp / 'src'
    d.mkdir()
    p = d / 'TaskStatusEnum.java'
    p.write_text(SRC_ENUM, encoding='utf-8')
    return tmp


class ManualFactsTest(unittest.TestCase):
    def _manual(self, tmp, table):
        p = tmp / '操作手册.md'
        p.write_text('# 手册\n\n## 3.2\n\n' + table, encoding='utf-8')
        return p

    def test_consistent_enum_passes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mk_src(tmp)
            manual = self._manual(tmp, (
                '| 状态 | 含义 |\n| --- | --- |\n'
                '| 待认领 | 等待认领 |\n| 待巡检 | 等待开始 |\n| 巡检中 | 进行中 |\n'
                '| 已完成 | 提交完成 |\n| 逾期待检 | 补检窗口 |\n| 巡检超时 | 补检超时 |\n'
                '| 未检 | 作废 |\n| 漏检 | 作废 |\n| 已完成（补检） | 补检完成 |\n| 未认领 | 补检无人 |\n'
            ))
            rep = run(manual, [str(tmp)])
            self.assertEqual(rep['status'], 'pass', rep['errors'])
            self.assertTrue(any(c['status'] == 'pass' for c in rep['checks']))

    def test_drift_intersection_one_warns(self):
        # 旧 4 状态场景：与源码交集只有「已完成」1 项 → 提示人工确认
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mk_src(tmp)
            manual = self._manual(tmp, (
                '| 状态 | 含义 |\n| --- | --- |\n'
                '| 待执行 | 未开始 |\n| 执行中 | 进行中 |\n| 已完成 | 完成 |\n| 已逾期 | 超时 |\n'
            ))
            rep = run(manual, [str(tmp)])
            self.assertTrue(any('待确认' in w or '人工确认' in w for w in rep['warnings']), rep['warnings'])

    def test_drift_partial_blocks(self):
        # 手册 6 项状态与源码 10 项部分重合且缺 4 项 → error
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mk_src(tmp)
            manual = self._manual(tmp, (
                '| 状态 | 含义 |\n| --- | --- |\n'
                '| 待认领 | a |\n| 待巡检 | b |\n| 巡检中 | c |\n| 已完成 | d |\n| 未检 | e |\n| 漏检 | f |\n'
            ))
            rep = run(manual, [str(tmp)])
            self.assertEqual(rep['status'], 'blocked')
            self.assertTrue(any('枚举漂移' in e for e in rep['errors']), rep['errors'])

    def test_field_table_silent(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mk_src(tmp)
            manual = self._manual(tmp, (
                '| 字段 | 必填 |\n| --- | --- |\n'
                '| 巡检点编号 | 是 |\n| 巡检点名称 | 是 |\n| 责任部门 | 是 |\n| 签到方式 | 是 |\n'
            ))
            rep = run(manual, [str(tmp)])
            self.assertEqual(rep['checks'], [])

    def test_extract_enum_blocks(self):
        manual = (
            '| 状态 | 含义 |\n| --- | --- |\n'
            '| 待认领 | a |\n| 待巡检 | b |\n| 巡检中 | c |\n'
        )
        blocks = extract_manual_enums(manual)
        self.assertTrue(any('待认领' in b[0] or any(x == '待认领' for x in b[1]) for b in blocks))


if __name__ == '__main__':
    unittest.main()
