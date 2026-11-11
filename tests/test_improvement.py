"""Bài 4: kiểm tra incident liên quan chưa đọc trước khi chấp nhận câu trả lời (lỗi thấy ở H1/H6)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

SOURCE = 'https://stspg.io/7pwv28hvkmz8'  # URL của h02n9572mx9y trong snapshot
READ_H02 = '{"provider":"github","incident_id":"h02n9572mx9y"}'  # update của incident này trỏ tới xr3myzj7ms51


class LinkedIncidentTests(unittest.TestCase):
    def test_linked_incident_is_requested_before_final(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', READ_H02),
                             final('Bản nháp: chưa rõ nguyên nhân. ' + SOURCE),
                             tool_call('2', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
                             final('Nguyên nhân nằm trong incident gộp. ' + SOURCE)])
        result = run_agent('Điều tra h02n9572mx9y', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(x['event'] == 'validation_unread_linked_incident' for x in result['trace']))
        self.assertIn('xr3myzj7ms51', fake.histories[2][-1]['content'])  # yêu cầu sửa đã gửi cho model
        self.assertEqual(len({x['step'] for x in result['trace'] if x['event'] == 'tool'}), 2)

    def test_reminder_is_sent_only_once(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', READ_H02),
                             final('Bản nháp. ' + SOURCE), final('Không cần đọc thêm. ' + SOURCE)])
        result = run_agent('x', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(sum(x['event'] == 'validation_unread_linked_incident' for x in result['trace']), 1)

    def test_no_reminder_when_budget_is_exhausted(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', READ_H02), final('Kết luận. ' + SOURCE)])
        self.assertEqual(run_agent('x', fake, StatusTools(), max_steps=2)['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
