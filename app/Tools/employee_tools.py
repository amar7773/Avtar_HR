from app.Services.Data_services import DataService
from datetime import datetime
import json
from zoneinfo import ZoneInfo


data_service = DataService()
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


# ==========================================
# Helper functions
# ==========================================

def clean_value(value):
    if value is None:
        return None

    try:
        import numpy as np
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        if isinstance(value, np.bool_):
            return bool(value)
    except Exception:
        pass

    try:
        if value != value:  # NaN check
            return None
    except Exception:
        pass

    return value


def format_india_datetime(value):
    value = clean_value(value)
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=INDIA_TIMEZONE)
        india_time = parsed.astimezone(INDIA_TIMEZONE)
        return india_time.strftime("%Y-%m-%d %I:%M %p IST")
    except (TypeError, ValueError):
        return str(value)


def date_only_value(value):
    value = clean_value(value)
    if value is None:
        return None
    return str(value).split("T", 1)[0].split(" ", 1)[0]


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
        return {"success": False, "message": "Employee not found."}

    employee = result.iloc[0]

    designation = data_service.get_employee_designation(employee_id)
    branch = data_service.get_employee_branch(employee_id)
    shift = data_service.get_employee_shift(employee_id)

    employee_data = {
        "employee_id": clean_value(employee["employeeId"]),
        "name": f"{employee['firstName']} {employee['lastName']}",
        "job_type": clean_value(employee["jobType"]),
        "joining_date": date_only_value(employee["dateOfJoining"]),
        "employment_status": clean_value(employee["employmentStatus"]),
        "status": clean_value(employee["status"]),
    }

    if not designation.empty:
        employee_data["designation"] = clean_value(designation.iloc[0]["name"])

    if not branch.empty:
        employee_data["branch"] = clean_value(branch.iloc[0]["name"])

    if not shift.empty:
        employee_data["shift"] = clean_value(shift.iloc[0]["shiftName"])
        employee_data["shift_start"] = clean_value(shift.iloc[0]["startTime"])
        employee_data["shift_end"] = clean_value(shift.iloc[0]["endTime"])

    return {"success": True, "employee": employee_data}


# ==========================================
# 2. Attendance
# ==========================================

def get_attendance(employee_id, date=None, month=None, year=None):

    result = data_service.get_attendance(
        employee_id=employee_id,
        date=date,
        month=month,
        year=year,
    )

    if result.empty:
        return {
            "success": True,
            "message": "No attendance records found.",
            "records": [],
        }

    result = result.sort_values("dateKey", ascending=False)
    total_records = len(result)

    # Determine the summary period
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

    lifeline_dates = {"late_check_in": [], "early_checkout": []}
    for _, row in summary_result.iterrows():
        for marker in lifeline_markers(row.get("lifelineApplied")):
            if marker in lifeline_dates:
                lifeline_dates[marker].append(str(row.get("dateKey")))

    records = []
    for _, row in result.head(10).iterrows():
        records.append({
            "date": clean_value(row.get("dateKey")),
            "check_in": format_india_datetime(row.get("checkInAt")),
            "check_out": format_india_datetime(row.get("checkOutAt")),
            "worked_minutes": clean_value(row.get("workedMinutes")),
            "status": str(clean_value(row.get("status")) or "").replace("_", " ").title(),
            "is_late": clean_value(row.get("isLate")),
            "late_by_minutes": clean_value(row.get("lateByMinutes")),
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
            "early_checkout_dates": lifeline_dates["early_checkout"],
        },
        "records": records,
    }


# ==========================================
# 3. Leave Requests
# ==========================================

def get_leave_requests(employee_id, status=None):

    result = data_service.get_leave_requests(
        employee_id=employee_id,
        status=status,
    )

    if result.empty:
        return {
            "success": True,
            "message": "No leave requests found.",
            "records": [],
        }

    records = []
    for _, row in result.iterrows():
        records.append({
            "from_date": clean_value(row.get("fromDate")),
            "to_date": clean_value(row.get("toDate")),
            "days": clean_value(row.get("days")),
            "reason": clean_value(row.get("reason")),
            "status": clean_value(row.get("status")),
            "is_half_day": clean_value(row.get("isHalfDay")),
            "half_day_session": clean_value(row.get("halfDaySession")),
        })

    return {"success": True, "records": records}


def get_leave_balance(employee_id):
    leave_types = data_service.get_leave_types()
    requests = data_service.get_leave_requests(employee_id)

    if leave_types.empty:
        return {
            "success": False,
            "message": "Leave entitlement data is not available.",
        }

    approved = (
        requests[requests["status"].astype(str).str.casefold() == "approved"]
        if not requests.empty
        else requests.iloc[0:0]
    )

    breakdown = []
    total_allocated = 0.0
    total_used = 0.0

    for _, row in leave_types.iterrows():
        lt_id = str(row.get("_id") or row.get("id"))
        alloc = float(row.get("daysPerYear") or 0)
        used = (
            float(
                approved[approved["leaveTypeId"].astype(str) == lt_id]["days"]
                .fillna(0)
                .sum()
            )
            if not approved.empty
            else 0.0
        )
        rem = max(alloc - used, 0.0)
        total_allocated += alloc
        total_used += used

        breakdown.append({
            "name": clean_value(row.get("name")),
            "code": clean_value(row.get("code")),
            "allocated": int(alloc) if alloc.is_integer() else alloc,
            "used": int(used) if used.is_integer() else used,
            "remaining": int(rem) if rem.is_integer() else rem,
        })

    total_remaining = max(total_allocated - total_used, 0.0)

    def _to_int_if_whole(v):
        return int(v) if float(v).is_integer() else v

    return {
        "success": True,
        "leave_types": breakdown,
        "total_allocated": _to_int_if_whole(total_allocated),
        "total_used": _to_int_if_whole(total_used),
        "total_remaining": _to_int_if_whole(total_remaining),
        "remaining_leaves": _to_int_if_whole(total_remaining),
        "allocated_leaves": _to_int_if_whole(total_allocated),
        "used_leaves": _to_int_if_whole(total_used),
    }


def get_lifeline_balance(employee_id, month=None, year=None):
    attendance = get_attendance(employee_id, month=month, year=year)

    if not attendance.get("records"):
        return {
            "success": False,
            "message": "No attendance data is available for lifeline calculation.",
        }

    shift = data_service.get_employee_shift(employee_id)
    if shift.empty:
        return {
            "success": False,
            "message": "Shift limits are not available for lifeline calculation.",
        }

    row = shift.iloc[0]
    late_limit = float(row.get("lateCheckInLifelinesPerMonth") or 0)
    early_limit = float(row.get("earlyCheckoutLifelinesPerMonth") or 0)
    summary = attendance.get("summary", {})

    late_remaining = max(late_limit - summary.get("late_check_in_lifelines", 0), 0)
    early_remaining = max(early_limit - summary.get("late_check_out_lifelines", 0), 0)

    def _to_int_if_whole(v):
        return int(v) if float(v).is_integer() else v

    return {
        "success": True,
        "late_check_in_remaining": _to_int_if_whole(late_remaining),
        "early_checkout_remaining": _to_int_if_whole(early_remaining),
        "period": attendance.get("summary", {}).get("month"),
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
            "days_per_year": clean_value(row.get("daysPerYear")),
            "is_paid": clean_value(row.get("isPaid")),
            "carry_forward": clean_value(row.get("carryForward")),
            "allow_half_day": clean_value(row.get("allowHalfDay")),
            "requires_approval": clean_value(row.get("requiresApproval")),
        })

    return {"success": True, "leave_types": records}


# ==========================================
# 5. Company Holidays
# ==========================================

def get_holidays(year=None, month=None):

    result = data_service.get_holidays(year=year, month=month)
    records = []

    for _, row in result.iterrows():
        records.append({
            "name": clean_value(row.get("name")),
            "date": clean_value(row.get("date")),
            "type": clean_value(row.get("type")),
            "description": clean_value(row.get("description")),
        })

    return {"success": True, "holidays": records}


# ==========================================
# 6. Employee Shift
# ==========================================

def get_employee_shift(employee_id):

    result = data_service.get_employee_shift(employee_id)

    if result.empty:
        return {"success": False, "message": "Shift information not found."}

    shift = result.iloc[0]

    return {
        "success": True,
        "shift": {
            "name": clean_value(shift.get("shiftName")),
            "start_time": clean_value(shift.get("startTime")),
            "end_time": clean_value(shift.get("endTime")),
            "grace_period_minutes": clean_value(shift.get("gracePeriodMinutes")),
            "working_days": clean_value(shift.get("workingDays")),
        },
    }


# ==========================================
# 7. Employee Branch
# ==========================================

def get_employee_branch(employee_id):

    result = data_service.get_employee_branch(employee_id)

    if result.empty:
        return {"success": False, "message": "Branch information not found."}

    branch = result.iloc[0]

    return {
        "success": True,
        "branch": {
            "name": clean_value(branch.get("name")),
            "city": clean_value(branch.get("address.city")),
            "state": clean_value(branch.get("address.state")),
            "country": clean_value(branch.get("address.country")),
        },
    }


# ==========================================
# 8. Employee Designation
# ==========================================

def get_employee_designation(employee_id):

    result = data_service.get_employee_designation(employee_id)

    if result.empty:
        return {"success": False, "message": "Designation information not found."}

    designation = result.iloc[0]

    return {
        "success": True,
        "designation": {
            "name": clean_value(designation.get("name")),
            "code": clean_value(designation.get("code")),
            "job_type": clean_value(designation.get("defaultJobType")),
            "level": clean_value(designation.get("level")),
            "portal_access": clean_value(designation.get("portalAccessEnabled")),
        },
    }