import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.Services.Data_services import DataService


def test_data_service():
    data_service = DataService()
    employee_id = 101

    attendance = data_service.get_attendance(employee_id)
    assert attendance is not None

    experience = data_service.get_experience(employee_id)
    assert experience is not None

    salary = data_service.get_salary(employee_id)
    assert salary is not None


if __name__ == "__main__":
    test_data_service()