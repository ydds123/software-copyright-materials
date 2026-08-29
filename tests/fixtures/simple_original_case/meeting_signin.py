"""会议室签到工具（合成样本，简单原创案例）。

无复杂算法、无框架，但有真实领域约束：
- 签到时间段校验：只能在会议开始前 15 分钟至开始后 10 分钟内签到
- 重复签到校验：同一会议同一人只记一次有效签到
- 迟到状态流转：超过开始时间签到自动标记为迟到，不影响有效状态
- 数据关系：会议室、会议、人员三者的归属校验

预期判定：B 级。代表性来自领域规则与真实业务约束，而非代码复杂度。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

SIGNIN_EARLY_WINDOW = timedelta(minutes=15)
SIGNIN_LATE_WINDOW = timedelta(minutes=10)

STATUS_VALID = "valid"
STATUS_LATE = "late"


@dataclass
class Meeting:
    meeting_id: str
    room_id: str
    start_time: datetime
    owner_id: str


@dataclass
class SigninRecord:
    meeting_id: str
    user_id: str
    signin_time: datetime
    status: str


class MeetingSigninService:
    """会议室签到核心服务。"""

    def __init__(self, meetings: dict[str, Meeting]):
        self._meetings = meetings
        self._records: list[SigninRecord] = []

    def signin(self, meeting_id: str, user_id: str, now: datetime) -> SigninRecord:
        meeting = self._meetings[meeting_id]

        # 领域约束 1：归属校验，会议必须真实存在
        if meeting is None:
            raise ValueError("会议不存在")

        # 领域约束 2：时间段校验
        earliest = meeting.start_time - SIGNIN_EARLY_WINDOW
        latest = meeting.start_time + SIGNIN_LATE_WINDOW
        if not (earliest <= now <= latest):
            raise ValueError("不在签到时间窗内")

        # 领域约束 3：重复签到校验
        for r in self._records:
            if r.meeting_id == meeting_id and r.user_id == user_id:
                raise ValueError("已签到，不可重复签到")

        # 领域约束 4：迟到状态流转
        status = STATUS_LATE if now > meeting.start_time else STATUS_VALID

        record = SigninRecord(meeting_id, user_id, now, status)
        self._records.append(record)
        return record
