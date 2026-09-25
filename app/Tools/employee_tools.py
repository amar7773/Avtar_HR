from app.Services.Data_services import DataService
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo


data_service = DataService()
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


# ==========================================
# Helper
# ==========================================

def clean_value(value):
    if value is None:
        return None

    try:
        if value != value:  # NaN
            return None
    except:
        pass

    return value


def format_india_datetime(value):
    value = clean_value(value)
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        india_time = parsed.astimezone(INDIA_TIMEZONE)
        return india_time.strftime("%Y-%m-%d %I:%M %p IST")
    except (TypeError, ValueError):
        return str(value)


def lifeline_markers(value):
    value = clean_value(value)
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


# ==========================================
# 1. Employee
# ==========================================

def get_employee(employee_id):

    result = data_service.get_employee(employee_id)

    if result.empty:
        return {
            "success": False,
            "message": "Employee not found."
        }

    employee = result.iloc[0]

    designation = data_service.get_employee_designation(
        employee_id
    )

    branch = data_service.get_employee_branch(
        employee_id
    )

    shift = data_service.get_employee_shift(
        employee_id
    )

    employee_data = {
        "employee_id": clean_value(employee["employeeId"]),
        "name": f"{employee['firstName']} {employee['lastName']}",
        "job_type": clean_value(employee["jobType"]),
        "joining_date": clean_value(employee["dateOfJoining"]),
        "employment_status": clean_value(
            employee["employmentStatus"]
        ),
        "status": clean_value(employee["status"])
    }

    if not designation.empty:
        employee_data["designation"] = clean_value(
            designation.iloc[0]["name"]
        )

    if not branch.empty:
        employee_data["branch"] = clean_value(
            branch.iloc[0]["name"]
        )

    if not shift.empty:
        employee_data["shift"] = clean_value(
            shift.iloc[0]["shiftName"]
        )

        employee_data["shift_start"] = clean_value(
            shift.iloc[0]["startTime"]
        )

        employee_data["shift_end"] = clean_value(
            shift.iloc[0]["endTime"]
        )

    return {
        "success": True,
        "employee": employee_data
    }


EMPLOYEE_TOOL = {
    "type": "function",
    "name": "get_employee",
    "description": "Get an employee's profile, designation, branch, shift and employment information.",
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "Employee ID such as EMP-0013"
            }
        },
        "required": ["employee_id"]
    }
}


# ==========================================
# 2. Attendance
# ==========================================

def get_attendance(
    employee_id,
    date=None,
    month=None,
    year=None
):

    result = data_service.get_attendance(
        employee_id=employee_id,
        date=date,
        month=month,
        year=year
    )

    if result.empty:
        return {
            "success": True,
            "message": "No attendance records found.",
            "records": []
        }

    result = result.sort_values("dateKey", ascending=False)
    total_records = len(result)
    summary_result = result
    summary_prefix = str(result.iloc[0].get("dateKey"))[:7]
    if not (month and year):
        summary_result = result[
            result["dateKey"].astype(str).str.startswith(summary_prefix)
        ]
    summary_status = summary_result["status"].astype(str).str.lower()
    worked_minutes = summary_result["workedMinutes"].fillna(0)
    total_worked_minutes = int(worked_minutes.sum())
    total_worked_hours = total_worked_minutes // 60
    remaining_worked_minutes = total_worked_minutes % 60
    lifelines = [
        marker
        for value in summary_result["lifelineApplied"]
        for marker in lifeline_markers(value)
    ]
    absent_dates = summary_result.loc[
        summary_status == "absent", "dateKey"
    ].astype(str).tolist()
    half_day_dates = summary_result.loc[
        summary_status == "half_day", "dateKey"
    ].astype(str).tolist()
    present_dates = summary_result.loc[
        summary_status == "present", "dateKey"
    ].astype(str).tolist()
    lifeline_dates = {
        "late_check_in": [],
        "early_checkout": []
    }
    for _, row in summary_result.iterrows():
        for marker in lifeline_markers(row.get("lifelineApplied")):
            if marker in lifeline_dates:
                lifeline_dates[marker].append(str(row.get("dateKey")))
    result = result.head(10)
    records = []

    for _, row in result.iterrows():

        records.append({
            "date": clean_value(row.get("dateKey")),
            "check_in": format_india_datetime(row.get("checkInAt")),
            "check_out": format_india_datetime(row.get("checkOutAt")),
            "worked_minutes": clean_value(
                row.get("workedMinutes")
            ),
            "status": str(clean_value(row.get("status")) or "").replace(
                "_", " "
            ).title(),
            "is_late": clean_value(row.get("isLate")),
            "late_by_minutes": clean_value(
                row.get("lateByMinutes")
            )
        })

    return {
        "success": True,
        "message": (
            f"Showing the {len(records)} most recent attendance records"
            f" out of {total_records} total records."
        ),
        "summary": {
            "month": summary_prefix,
            "total_records": len(summary_result),
            "present": int((summary_status == "present").sum()),
            "absent": int((summary_status == "absent").sum()),
            "half_day": int((summary_status == "half_day").sum()),
            "total_worked_minutes": total_worked_minutes,
            "total_worked_hours": total_worked_hours,
            "remaining_worked_minutes": remaining_worked_minutes,
            "late_check_in_lifelines": lifelines.count("late_check_in"),
            "late_check_out_lifelines": lifelines.count("early_checkout"),
            "absent_dates": absent_dates,
            "half_day_dates": half_day_dates,
            "present_dates": present_dates,
            "late_check_in_dates": lifeline_dates["late_check_in"],
            "early_checkout_dates": lifeline_dates["early_checkout"]
        },
        "records": records
    }


ATTENDANCE_TOOL = {
    "type": "function",
    "name": "get_attendance",
    "description": "Get an employee's attendance records. Can filter by date, month and year.",
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "Employee ID such as EMP-0013"
            },
            "date": {
                "type": ["string", "null"],
                "description": "Specific date in YYYY-MM-DD format"
            },
            "month": {
                "type": ["integer", "null"],
                "description": "Month number"
            },
            "year": {
                "type": ["integer", "null"],
                "description": "Year"
            }
        },
        "required": [
            "employee_id",
            "date",
            "month",
            "year"
        ]
    }
}


# ==========================================
# 3. Leave Requests
# ==========================================

def get_leave_requests(
    employee_id,
    status=None
):

    result = data_service.get_leave_requests(
        employee_id=employee_id,
        status=status
    )

    if result.empty:
        return {
            "success": True,
            "message": "No leave requests found.",
            "records": []
        }

    records = []

    for _, row in result.iterrows():

        records.append({
            "from_date": clean_value(row.get("fromDate")),
            "to_date": clean_value(row.get("toDate")),
            "days": clean_value(row.get("days")),
            "reason": clean_value(row.get("reason")),
            "status": clean_value(row.get("status")),
            "is_half_day": clean_value(
                row.get("isHalfDay")
            ),
            "half_day_session": clean_value(
                row.get("halfDaySession")
            )
        })

    return {
        "success": True,
        "records": records
    }


LEAVE_REQUEST_TOOL = {
    "type": "function",
    "name": "get_leave_requests",
    "description": "Get an employee's valid leave requests.",
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "Employee ID such as EMP-0013"
            },
            "status": {
                "type": ["string", "null"],
                "description": "approved, rejected, pending or cancelled"
            }
        },
        "required": [
            "employee_id",
            "status"
        ]
    }
}


# ==========================================
# 4. Leave Types / Policy
# ==========================================

def get_leave_types():

    result = data_service.get_leave_types()

    records = []

    for _, row in result.iterrows():

        records.append({
            "name": clean_value(row.get("name")),
            "code": clean_value(row.get("code")),
            "days_per_year": clean_value(
                row.get("daysPerYear")
            ),
            "is_paid": clean_value(
                row.get("isPaid")
            ),
            "carry_forward": clean_value(
                row.get("carryForward")
            ),
            "allow_half_day": clean_value(
                row.get("allowHalfDay")
            ),
            "requires_approval": clean_value(
                row.get("requiresApproval")
            )
        })

    return {
        "success": True,
        "leave_types": records
    }


LEAVE_TYPES_TOOL = {
    "type": "function",
    "name": "get_leave_types",
    "description": "Get active company leave types and leave policies.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


# ==========================================
# 5. Company Holidays
# ==========================================

def get_holidays(
    year=None,
    month=None
):

    result = data_service.get_holidays(
        year=year,
        month=month
    )

    records = []

    for _, row in result.iterrows():

        records.append({
            "name": clean_value(row.get("name")),
            "date": clean_value(row.get("date")),
            "type": clean_value(row.get("type")),
            "description": clean_value(
                row.get("description")
            )
        })

    return {
        "success": True,
        "holidays": records
    }


HOLIDAY_TOOL = {
    "type": "function",
    "name": "get_holidays",
    "description": "Get active company holidays by year or month.",
    "parameters": {
        "type": "object",
        "properties": {
            "year": {
                "type": ["integer", "null"],
                "description": "Year such as 2026"
            },
            "month": {
                "type": ["integer", "null"],
                "description": "Month number"
            }
        },
        "required": [
            "year",
            "month"
        ]
    }
}


# ==========================================
# 6. Employee Shift
# ==========================================

def get_employee_shift(employee_id):

    result = data_service.get_employee_shift(
        employee_id
    )

    if result.empty:
        return {
            "success": False,
            "message": "Shift information not found."
        }

    shift = result.iloc[0]

    return {
        "success": True,
        "shift": {
            "name": clean_value(
                shift.get("shiftName")
            ),
            "start_time": clean_value(
                shift.get("startTime")
            ),
            "end_time": clean_value(
                shift.get("endTime")
            ),
            "grace_period_minutes": clean_value(
                shift.get("gracePeriodMinutes")
            ),
            "working_days": clean_value(
                shift.get("workingDays")
            )
        }
    }


SHIFT_TOOL = {
    "type": "function",
    "name": "get_employee_shift",
    "description": "Get an employee's assigned shift and working hours.",
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string"
            }
        },
        "required": ["employee_id"]
    }
}


# ==========================================
# 7. Employee Branch
# ==========================================

def get_employee_branch(employee_id):

    result = data_service.get_employee_branch(
        employee_id
    )

    if result.empty:
        return {
            "success": False,
            "message": "Branch information not found."
        }

    branch = result.iloc[0]

    return {
        "success": True,
        "branch": {
            "name": clean_value(
                branch.get("name")
            ),
            "city": clean_value(
                branch.get("address.city")
            ),
            "state": clean_value(
                branch.get("address.state")
            ),
            "country": clean_value(
                branch.get("address.country")
            )
        }
    }


BRANCH_TOOL = {
    "type": "function",
    "name": "get_employee_branch",
    "description": "Get an employee's assigned branch.",
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string"
            }
        },
        "required": ["employee_id"]
    }
}


# ==========================================
# 8. Employee Designation
# ==========================================

def get_employee_designation(employee_id):

    result = data_service.get_employee_designation(
        employee_id
    )

    if result.empty:
        return {
            "success": False,
            "message": "Designation information not found."
        }

    designation = result.iloc[0]

    return {
        "success": True,
        "designation": {
            "name": clean_value(
                designation.get("name")
            ),
            "code": clean_value(
                designation.get("code")
            ),
            "job_type": clean_value(
                designation.get("defaultJobType")
            ),
            "level": clean_value(
                designation.get("level")
            ),
            "portal_access": clean_value(
                designation.get("portalAccessEnabled")
            )
        }
    }


DESIGNATION_TOOL = {
    "type": "function",
    "name": "get_employee_designation",
    "description": "Get an employee's designation information.",
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string"
            }
        },
        "required": ["employee_id"]
    }
}