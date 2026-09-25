from app.Tools.employee_tools import (
    get_employee,
    get_attendance,
    get_leave_requests,
    get_leave_types,
    get_holidays,
    get_employee_shift,
    get_employee_branch,
    get_employee_designation
)


employee_id = "EMP-0013"


print("\n========== EMPLOYEE ==========")
print(get_employee(employee_id))


print("\n========== ATTENDANCE ==========")
print(get_attendance(employee_id))


print("\n========== LEAVE REQUESTS ==========")
print(get_leave_requests(employee_id))


print("\n========== LEAVE TYPES ==========")
print(get_leave_types())


print("\n========== HOLIDAYS ==========")
print(get_holidays(year=2026))


print("\n========== SHIFT ==========")
print(get_employee_shift(employee_id))


print("\n========== BRANCH ==========")
print(get_employee_branch(employee_id))


print("\n========== DESIGNATION ==========")
print(get_employee_designation(employee_id))