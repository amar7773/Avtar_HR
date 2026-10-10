import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.Tools.employee_tools import (
    get_employee,
    get_attendance,
    get_leave_requests,
    get_leave_types,
    get_holidays,
    get_employee_shift,
    get_employee_branch,
    get_employee_designation,
)


def test_employee_tools():
    employee_id = "EMP-0013"
    emp = get_employee(employee_id)
    assert emp is not None

    att = get_attendance(employee_id)
    assert att is not None

    reqs = get_leave_requests(employee_id)
    assert reqs is not None

    types = get_leave_types()
    assert types is not None

    hols = get_holidays(year=2026)
    assert hols is not None

    shift = get_employee_shift(employee_id)
    assert shift is not None

    branch = get_employee_branch(employee_id)
    assert branch is not None

    des = get_employee_designation(employee_id)
    assert des is not None


if __name__ == "__main__":
    test_employee_tools()