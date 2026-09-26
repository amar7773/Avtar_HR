from pathlib import Path

from app.Data_Source.csv_source import CSVDataSource


class DataService:

    def __init__(self):
        project_root = Path(__file__).resolve().parents[2]
        self.source = CSVDataSource(project_root / "Data")

    # Employee
    def get_employee(self, employee_id):

        data = self.source.get_data("employees")

        return data[
            data["employeeId"] == employee_id
        ]

    def get_company_employees(self, include_inactive=False):
        employees = self.source.get_data("employees")
        result = employees[employees["isDeleted"] == False]
        if not include_inactive and "status" in result.columns:
            result = result[
                result["status"].astype(str).str.casefold() == "active"
            ]
        return result

    @staticmethod
    def _employee_keys(employee_id):
        """Return safe aliases used by the small CSV exports."""
        value = str(employee_id).strip()
        keys = {value}
        if value.upper().startswith("EMP-"):
            digits = value.split("-", 1)[1]
            if digits.isdigit():
                keys.update({digits, str(int(digits)), str(int(digits) + 100)})
        elif value.isdigit():
            keys.add(f"EMP-{int(value):04d}")
        return keys

    def _simple_employee_filter(self, frame, employee_id):
        if frame.empty or "employee_id" not in frame.columns:
            return frame.iloc[0:0]
        keys = self._employee_keys(employee_id)
        return frame[frame["employee_id"].astype(str).isin(keys)]

    def get_salary(self, employee_id, month=None, year=None):
        result = self._simple_employee_filter(
            self.source.get_data("salary"), employee_id
        )
        if month:
            month_names = (
                "january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november", "december"
            )
            names = {str(month).lower(), str(month).capitalize()}
            if isinstance(month, int) and 1 <= month <= 12:
                names.add(month_names[month - 1].capitalize())
            result = result[result["month"].astype(str).isin(names)]
        return result

    def get_projects(self, employee_id, status=None):
        result = self._simple_employee_filter(
            self.source.get_data("projects"), employee_id
        )
        if status:
            result = result[
                result["status"].astype(str).str.casefold() == status.casefold()
            ]
        return result

    def get_experience(self, employee_id):
        employee = self.get_employee(employee_id)
        if employee.empty:
            return employee.iloc[0:0]
        row = employee.iloc[0]
        return employee.assign(
            experience_employee_id=row.get("employeeId"),
            experience_joining_date=row.get("dateOfJoining"),
        )[["experience_employee_id", "experience_joining_date"]]

    # Attendance
    def get_attendance(
        self,
        employee_id,
        date=None,
        month=None,
        year=None
    ):

        employees = self.source.get_data("employees")
        attendance = self.source.get_data("attendancerecords")

        employee = employees[
            employees["employeeId"] == employee_id
        ]

        if employee.empty:
            return attendance.iloc[0:0]

        mongo_employee_id = employee.iloc[0]["_id"]

        result = attendance[
            attendance["employeeId"] == mongo_employee_id
        ]

        if date:
            result = result[
                result["dateKey"].astype(str) == date
            ]

        if month and year:
            result = result[
                result["dateKey"]
                .astype(str)
                .str.startswith(f"{year}-{month:02d}")
            ]

        elif year:
            result = result[
                result["dateKey"]
                .astype(str)
                .str.startswith(str(year))
            ]

        return result

    # Leave Requests
    def get_leave_requests(
        self,
        employee_id,
        status=None
    ):

        employees = self.source.get_data("employees")
        leaves = self.source.get_data("leaverequests")

        employee = employees[
            employees["employeeId"] == employee_id
        ]

        if employee.empty:
            return leaves.iloc[0:0]

        mongo_employee_id = employee.iloc[0]["_id"]

        result = leaves[
            leaves["employeeId"] == mongo_employee_id
        ]

        result = result[
            result["isDeleted"] == False
        ]

        if status:
            result = result[
                result["status"]
                .astype(str)
                .str.lower() == status.lower()
            ]

        return result

    # Leave Types
    def get_leave_types(self):

        data = self.source.get_data(
            "companyleavetypes"
        )

        return data[
            (data["isDeleted"] == False) &
            (data["status"].astype(str).str.lower() == "active")
        ]

    # Holidays
    def get_holidays(
        self,
        year=None,
        month=None
    ):

        data = self.source.get_data(
            "companyholidays"
        )

        result = data[
            (data["isDeleted"] == False) &
            (data["status"].astype(str).str.lower() == "active")
        ]

        if year:
            result = result[
                result["date"]
                .astype(str)
                .str.startswith(str(year))
            ]

        if month and year:
            result = result[
                result["date"]
                .astype(str)
                .str.startswith(f"{year}-{month:02d}")
            ]

        return result

    # Employee Shift
    def get_employee_shift(self, employee_id):

        employees = self.source.get_data("employees")
        shifts = self.source.get_data("companyshifts")

        employee = employees[
            employees["employeeId"] == employee_id
        ]

        if employee.empty:
            return shifts.iloc[0:0]

        shift_id = employee.iloc[0]["shiftId"]

        return shifts[
            shifts["_id"] == shift_id
        ]

    # Employee Branch
    def get_employee_branch(self, employee_id):

        employees = self.source.get_data("employees")
        branches = self.source.get_data("companybranches")

        employee = employees[
            employees["employeeId"] == employee_id
        ]

        if employee.empty:
            return branches.iloc[0:0]

        branch_id = employee.iloc[0]["branchId"]

        return branches[
            branches["_id"] == branch_id
        ]

    # Employee Designation
    def get_employee_designation(self, employee_id):

        employees = self.source.get_data("employees")
        designations = self.source.get_data(
            "companydesignations"
        )

        employee = employees[
            employees["employeeId"] == employee_id
        ]

        if employee.empty:
            return designations.iloc[0:0]

        designation_id = employee.iloc[0]["designationId"]

        return designations[
            designations["_id"] == designation_id
        ]