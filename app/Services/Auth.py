from app.Services.Data_services import DataService
from app.Tools.employee_tools import date_only_value
from pandas import isna


class AuthService:

    def __init__(self):
        self.data_service = DataService()

    @staticmethod
    def _clean_value(value, default=""):
        if isna(value):
            return default
        return value

    def login(self, employee_id):

        employee_id = str(employee_id).strip()

        if not employee_id:
            return {
                "success": False,
                "message": "Employee ID is required."
            }

        employee_data = self.data_service.get_employee(employee_id)

        if employee_data.empty:
            return {
                "success": False,
                "message": "Employee ID not found."
            }

        employee = employee_data.iloc[0]

        designation_data = self.data_service.get_employee_designation(
            employee_id
        )

        designation = "Not available"

        if not designation_data.empty:
            designation = str(
                designation_data.iloc[0].get("name", "Not available")
            )

        first_name = str(
            self._clean_value(employee.get("firstName", ""))
        ).strip()
        last_name = str(
            self._clean_value(employee.get("lastName", ""))
        ).strip()

        name = f"{first_name} {last_name}".strip()

        return {
            "success": True,
            "message": "Login successful.",
            "employee": {
                "employee_id": str(
                    self._clean_value(employee.get("employeeId", ""))
                ),
                "name": name,
                "first_name": first_name,
                "last_name": last_name,
                "designation": designation,
                "designation_id": str(
                    self._clean_value(employee.get("designationId", ""))
                ),
                "department_id": str(
                    self._clean_value(employee.get("departmentId", ""))
                ),
                "branch_id": str(
                    self._clean_value(employee.get("branchId", ""))
                ),
                "shift_id": str(
                    self._clean_value(employee.get("shiftId", ""))
                ),
                "joining_date": str(
                    date_only_value(
                        self._clean_value(employee.get("dateOfJoining", ""))
                    )
                ),
                "employment_status": str(
                    self._clean_value(employee.get("employmentStatus", ""))
                ),
                "status": str(
                    self._clean_value(employee.get("status", ""))
                ),
                "job_type": str(
                    self._clean_value(employee.get("jobType", ""))
                ),
                "management_level": self._clean_value(
                    employee.get("managementLevel", "")
                )
            }
        }