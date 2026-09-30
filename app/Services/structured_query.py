"""Deterministic routing for exact employee data queries.

This layer deliberately runs before the LLM. It prevents a generative model
from guessing values and keeps the payload sent to the model small and precise.
"""
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

from app.Services.Data_services import DataService
from app.Tools.employee_tools import (
    date_only_value,
    format_india_datetime,
    get_attendance as attendance_tool,
    get_leave_balance as leave_balance_tool,
    get_leave_requests as leave_requests_tool,
    get_leave_types as leave_types_tool,
    get_lifeline_balance as lifeline_balance_tool,
    get_employee as employee_tool,
    get_employee_shift as shift_tool,
    get_employee_branch as branch_tool,
    get_employee_designation as designation_tool,
    get_holidays as holidays_tool,
)


MONTHS = {
    name: number for number, name in enumerate(
        ("january", "february", "march", "april", "may", "june",
         "july", "august", "september", "october", "november", "december"),
        1,
    )
}
MONTHS.update({name[:3]: number for name, number in list(MONTHS.items())})
HINDI_MONTHS = {
    "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9,
    "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12
}
ALL_MONTHS = {**MONTHS, **HINDI_MONTHS}
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


class StructuredQueryRouter:
    """Parse and route employee queries deterministically to exact tools."""

    DATA_FIELDS = {
        "attendance": {
            "date": ("dateKey", "date"), "status": ("status",),
            "check_in": ("checkInAt", "check_in"), "check_out": ("checkOutAt", "check_out"),
            "worked_minutes": ("workedMinutes", "worked_minutes"),
            "is_late": ("isLate", "is_late"),
        },
        "salary": {
            "month": ("month",), "basic": ("basic",), "allowance": ("allowance",),
            "deduction": ("deduction",), "net_salary": ("net_salary",),
        },
        "projects": {
            "project_name": ("project_name",), "technology": ("technology",),
            "start_date": ("start_date",), "end_date": ("end_date",), "status": ("status",),
        },
        "leave": {
            "status": ("status",), "from_date": ("fromDate",),
            "to_date": ("toDate",), "days": ("days",), "reason": ("reason",),
        },
    }

    def __init__(self, data_service=None):
        self.data = data_service or DataService()
        self._context = {}

    @staticmethod
    def _date_filters(query, default_year=None):
        q = query.casefold()
        today = datetime.now(INDIA_TIMEZONE).date()

        if "today" in q or "आज" in q:
            return {"date": today.isoformat()}
        if "yesterday" in q or "kal" in q or "कल" in q:
            return {"date": (today - timedelta(days=1)).isoformat()}
        if "this month" in q or "current month" in q or "iss month" in q or "is month" in q:
            return {"month": today.month, "year": today.year}
        if "last month" in q or "previous month" in q or "pichle month" in q:
            previous = today.replace(day=1) - timedelta(days=1)
            return {"month": previous.month, "year": previous.year}

        # 1. YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD
        match_ymd = re.search(r"\b(20\d{2})[\s\-/.]+(\d{1,2})[\s\-/.]+(\d{1,2})\b", q)
        if match_ymd:
            y, m, d = int(match_ymd.group(1)), int(match_ymd.group(2)), int(match_ymd.group(3))
            return {"date": f"{y:04d}-{m:02d}-{d:02d}"}

        # 2. DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
        match_dmy = re.search(r"\b(\d{1,2})[\s\-/.]+(\d{1,2})[\s\-/.]+(20\d{2})\b", q)
        if match_dmy:
            d, m, y = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
            return {"date": f"{y:04d}-{m:02d}-{d:02d}"}

        month_names_pattern = "|".join(sorted(ALL_MONTHS.keys(), key=len, reverse=True))

        # 3. Day Month: e.g. "22 September", "22 Sep", "22nd September 2026"
        match_dm = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?[\s/,-]+(" + month_names_pattern + r")(?:\b|[\s/,-]+(20\d{2})\b)",
            q,
        )
        if match_dm:
            day = int(match_dm.group(1))
            month_name = match_dm.group(2)
            month = ALL_MONTHS.get(month_name)
            year = int(match_dm.group(3)) if match_dm.group(3) else (default_year or today.year)
            return {"date": f"{year:04d}-{month:02d}-{day:02d}"}

        # 4. Month Day: e.g. "September 22", "Sep 22", "September 22nd 2026"
        match_md = re.search(
            r"\b(" + month_names_pattern + r")[\s/,-]+(\d{1,2})(?:st|nd|rd|th)?(?:\b|[\s/,-]+(20\d{2})\b)",
            q,
        )
        if match_md:
            month_name = match_md.group(1)
            day = int(match_md.group(2))
            month = ALL_MONTHS.get(month_name)
            year = int(match_md.group(3)) if match_md.group(3) else (default_year or today.year)
            return {"date": f"{year:04d}-{month:02d}-{day:02d}"}

        # 5. Month only: e.g. "September", "September 2026", "in Sep"
        match_m = re.search(
            r"\b(" + month_names_pattern + r")(?:\b|[\s/,-]+(20\d{2})\b)",
            q,
        )
        if match_m:
            month_name = match_m.group(1)
            month = ALL_MONTHS.get(month_name)
            year = int(match_m.group(2)) if match_m.group(2) else (default_year or today.year)
            return {"month": month, "year": year}

        return {}

    @staticmethod
    def _fields(query, kind):
        q = query.casefold()
        aliases = {
            "date": ("date", "दिन", "तारीख"), "status": ("status", "स्थिति"),
            "check_in": ("check in", "check-in", "प्रवेश"),
            "check_out": ("check out", "check-out", "निकास"),
            "worked_minutes": ("worked minute", "worked time", "काम का समय"),
            "basic": ("basic", "मूल"), "allowance": ("allowance", "भत्ता"),
            "deduction": ("deduction", "कटौती"), "net_salary": ("net salary", "salary", "वेतन"),
            "month": ("month", "महीना"), "project_name": ("project", "परियोजना"),
            "technology": ("technology", "tech", "तकनीक"), "start_date": ("start date",),
            "end_date": ("end date",),
            "from_date": ("from date", "शुरू"), "to_date": ("to date", "अंत"),
            "days": ("days", "दिन"), "reason": ("reason", "कारण"),
        }
        selected = [field for field in StructuredQueryRouter.DATA_FIELDS[kind]
                    if any(term in q for term in aliases.get(field, (field,)))]
        return selected or list(StructuredQueryRouter.DATA_FIELDS[kind])

    def route(self, query, employee_id, conversation_history=None):
        q = query.casefold()
        normalized = re.sub(r"[\s-]+", " ", q)
        normalized = normalized.replace("checkin", "check in").replace("checkout", "check out")
        normalized = normalized.replace("lifline", "lifeline").replace("chek", "check").replace("cehck", "check")
        normalized = normalized.replace("shifiting", "shifting")

        ctx = self._context.setdefault(str(employee_id), {})
        latest_year = self._latest_year(employee_id)

        # Company employee count / listing queries
        company_employee_query = (
            any(term in normalized for term in (
                "company employee", "employees in company",
                "company employees", "employees in my company",
                "total employee", "employee count", "employee names", "employees count",
                "all employee", "employees name", "staff count",
                "company me kitne employee", "company mein kitne employee",
                "sabke name", "सभी कर्मचारी", "कुल कर्मचारी",
            ))
            or (
                "company" in normalized
                and ("employee" in normalized or "employees" in normalized)
                and any(term in normalized for term in ("total", "count", "how many", "kitne", "name", "names", "sabke"))
            )
            and not any(term in normalized for term in ("my employee", "my profile", "mera employee"))
        )
        if company_employee_query:
            frame = self.data.get_company_employees(
                include_inactive=any(term in normalized for term in ("inactive", "all employees", "सभी"))
            )
            if frame.empty:
                return self._missing("company employee")
            records = []
            for _, row in frame.iterrows():
                name = " ".join(
                    str(value).strip()
                    for value in (row.get("firstName"), row.get("lastName"))
                    if value == value and str(value).strip()
                )
                records.append({
                    "employee_id": row.get("employeeId"),
                    "name": name,
                })
            data = {"total_employees": len(records)}
            if any(term in normalized for term in ("name", "names", "sabke", "सभी")):
                data["employees"] = records
            return self._result("get_company_employees", data)

        if "company" in normalized and "name" in normalized and not any(w in normalized for w in ("holiday", "leave")):
            return self._missing(
                "company name",
                "Company name is not available in the connected company data."
            )

        # Date extraction with fallback to context
        filters = self._date_filters(normalized, default_year=latest_year)

        # Handle follow-up relative/ordinal questions like "What about 22nd?"
        if not filters.get("date") and not filters.get("month"):
            m_ord = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", normalized)
            if m_ord and ctx.get("last_month"):
                d = int(m_ord.group(1))
                m = ctx["last_month"]
                y = ctx.get("last_year", latest_year)
                filters["date"] = f"{y:04d}-{m:02d}-{d:02d}"

        # If a single-day query has no explicit date, inherit previous date from context
        single_day_terms = (
            "check in", "check-in", "check out", "check-out",
            "was i present", "was i absent", "present tha", "absent tha",
            "what time", "timing", "how many hours", "hours did i work",
            "worked hours", "kitne ghante", "us din", "that day", "same day", "usi date"
        )
        if not filters.get("date") and not filters.get("month"):
            if any(term in normalized for term in single_day_terms) and ctx.get("last_date"):
                filters["date"] = ctx["last_date"]

        # Update context dates
        if filters.get("date"):
            ctx["last_date"] = filters["date"]
        elif filters.get("month"):
            ctx["last_month"] = filters["month"]
            ctx["last_year"] = filters.get("year", latest_year)

        # =========================================================
        # 1. MODULE: HOLIDAYS
        # =========================================================
        holiday_terms = (
            "holiday", "holidays", "upcoming holidays", "company holidays",
            "holiday list", "list of holidays", "त्योहार", "छुट्टी सूची"
        )
        if any(term in normalized for term in holiday_terms) and not any(
            w in normalized for w in ("leave balance", "remaining leave", "applied leave", "apply leave", "leaves left")
        ):
            holidays = holidays_tool(year=filters.get("year"), month=filters.get("month"))
            ctx["kind"] = "holiday"
            return self._result("get_holidays", holidays)

        # =========================================================
        # 2. MODULE: SHIFT
        # =========================================================
        shift_terms = (
            "my shift", "shift timing", "shift time", "assigned shift",
            "duty timing", "duty time", "what is my shift", "show my shift",
            "shift details", "shifting"
        )
        if any(term in normalized for term in shift_terms) and not any(
            w in normalized for w in ("attendance", "check in on", "check out on")
        ):
            shift_res = shift_tool(employee_id)
            if not shift_res.get("success"):
                return self._missing("shift", shift_res.get("message"))
            ctx["kind"] = "shift"
            return self._result("get_employee_shift", shift_res.get("shift", {}))

        # =========================================================
        # 3. MODULE: BRANCH
        # =========================================================
        branch_terms = (
            "my branch", "office branch", "registered branch", "branch location",
            "office location", "work branch", "kaunsi branch", "what is my branch",
            "where is my branch"
        )
        if any(term in normalized for term in branch_terms):
            branch_res = branch_tool(employee_id)
            if not branch_res.get("success"):
                return self._missing("branch", branch_res.get("message"))
            ctx["kind"] = "branch"
            return self._result("get_employee_branch", branch_res.get("branch", {}))

        # =========================================================
        # 4. MODULE: DESIGNATION
        # =========================================================
        designation_terms = (
            "my designation", "current designation", "my role", "job role",
            "post", "my post", "पद", "kaunsi post", "kya designation",
            "what is my designation", "what is my role"
        )
        if any(term in normalized for term in designation_terms):
            des_res = designation_tool(employee_id)
            if not des_res.get("success"):
                return self._missing("designation", des_res.get("message"))
            ctx["kind"] = "designation"
            return self._result("get_employee_designation", des_res.get("designation", {}))

        # =========================================================
        # 5. MODULE: LEAVE
        # =========================================================
        leave_balance_terms = (
            "leave balance", "remaining leave", "remaining leaves", "leaves left",
            "leave left", "how many leaves", "leaves do i have", "kitni leave",
            "kitni leaves", "leave bachi", "leaves bachi", "meri leave", "mera leave",
            "chutti bachi", "chhutti bachi", "kitni chutti", "kitni chhutti",
            "balance leave", "balance leaves", "total leaves left", "leave count"
        )
        leave_types_terms = (
            "leave type", "leave types", "leave policy", "leave rules",
            "which leaves", "what leaves", "types of leave", "leaves available",
            "available leaves", "available leave", "छुट्टी के प्रकार", "छुट्टी नीति"
        )
        leave_request_terms = (
            "leave request", "leave requests", "leave history", "applied leave",
            "applied leaves", "pending leave", "approved leave", "rejected leave",
            "leave status", "leave application"
        )

        is_leave_query = (
            any(w in normalized for w in leave_balance_terms)
            or any(w in normalized for w in leave_types_terms)
            or any(w in normalized for w in leave_request_terms)
            or ("leave" in normalized and not any(w in normalized for w in ("attendance", "check in", "check out", "shift", "holiday")))
        )

        if is_leave_query:
            ctx["kind"] = "leave"
            if any(w in normalized for w in leave_types_terms):
                return self._result("get_leave_types", leave_types_tool())

            if any(w in normalized for w in leave_request_terms) and not any(w in normalized for w in leave_balance_terms):
                status = next((s for s in ("approved", "rejected", "pending", "cancelled") if s in normalized), None)
                req_res = leave_requests_tool(employee_id=employee_id, status=status)
                return self._result("get_leave_requests", req_res)

            # Default for leave is leave balance
            balance = leave_balance_tool(employee_id)
            if not balance.get("success"):
                return self._missing("leave balance", balance.get("message"))
            return self._result("get_leave_balance", {k: v for k, v in balance.items() if k != "success"})

        # =========================================================
        # 6. MODULE: EMPLOYEE PROFILE
        # =========================================================
        profile_terms = (
            "my profile", "employee profile", "my details", "employee details",
            "joining date", "date of joining", "job type", "employment status",
            "kab join", "joining kab"
        )
        if any(term in normalized for term in profile_terms):
            emp_res = employee_tool(employee_id)
            if not emp_res.get("success"):
                return self._missing("employee", emp_res.get("message"))
            ctx["kind"] = "profile"
            return self._result("get_employee", emp_res.get("employee", {}))

        # =========================================================
        # 7. MODULE: SALARY
        # =========================================================
        salary_terms = ("salary", "वेतन", "pay", "payslip", "tankhah", "salary slip")
        if any(term in normalized for term in salary_terms):
            frame = self.data.get_salary(employee_id, month=filters.get("month"))
            if frame.empty:
                return self._missing("salary", filters)
            ctx["kind"] = "salary"
            fields = self._fields(query, "salary")
            records = []
            for _, row in frame.iterrows():
                record = {}
                for field in fields:
                    source = next((col for col in self.DATA_FIELDS["salary"][field] if col in row), None)
                    if source:
                        val = row[source]
                        record[field] = None if val != val else val
                records.append(record)
            return self._result("get_salary", {"records": records, "filters": filters})

        # =========================================================
        # 8. MODULE: ATTENDANCE
        # =========================================================
        attendance_terms = (
            "attendance", "check in", "check-in", "check out", "check-out",
            "present", "absent", "half day", "hours", "worked", "lifeline",
            "उपस्थिति", "हाजिरी", "worked minutes", "working time", "working hours",
            "late", "last attendance"
        )
        is_attendance_query = any(term in normalized for term in attendance_terms) or bool(filters.get("date"))

        if is_attendance_query:
            ctx["kind"] = "attendance"

            # 8a. Lifeline balance
            if "lifeline" in normalized and any(term in normalized for term in ("remaining", "left", "bachi", "balance")):
                balance_result = lifeline_balance_tool(employee_id, month=filters.get("month"), year=filters.get("year"))
                if not balance_result.get("success"):
                    return self._missing("lifeline balance", balance_result.get("message"))
                return self._result("get_attendance_summary", balance_result)

            # 8b. EXACT DATE-SPECIFIC ATTENDANCE
            if filters.get("date"):
                date = filters["date"]
                ctx["last_date"] = date
                # Call attendance tool with ONLY employee_id and date
                exact = attendance_tool(employee_id=employee_id, date=date)
                records = exact.get("records", [])
                record = records[0] if records else None

                # Determine exact query intent
                if any(w in normalized for w in ("check in", "check-in", "in time")):
                    q_intent = "check_in"
                elif any(w in normalized for w in ("check out", "check-out", "out time")):
                    q_intent = "check_out"
                elif any(w in normalized for w in (
                    "how many hours", "hours did i work", "working hours",
                    "total hours", "kitne ghante", "worked hours", "hours worked"
                )):
                    q_intent = "worked_hours"
                elif any(w in normalized for w in (
                    "was i present", "was i absent", "present tha", "absent tha",
                    "half day tha", "presence", "present on", "absent on"
                )):
                    q_intent = "presence"
                else:
                    q_intent = "date_attendance"

                if record:
                    w_min = int(record.get("worked_minutes") or 0)
                    clean_rec = {
                        "date": record.get("date"),
                        "status": record.get("status"),
                        "check_in": record.get("check_in"),
                        "check_out": record.get("check_out"),
                        "worked_hours": w_min // 60,
                        "worked_minutes": w_min % 60,
                        "total_worked_minutes": w_min,
                        "is_late": record.get("is_late"),
                        "late_by_minutes": record.get("late_by_minutes"),
                    }
                    return self._result("get_attendance", {
                        "query_intent": q_intent,
                        "date": date,
                        "found": True,
                        "record": clean_rec,
                        "records": [clean_rec],
                    })
                else:
                    return self._result("get_attendance", {
                        "query_intent": q_intent,
                        "date": date,
                        "found": False,
                        "record": None,
                        "records": [],
                        "message": f"No attendance record found for {date}."
                    })

            # 8c. TOTAL ATTENDANCE COUNT ("What is my total attendance?")
            if any(w in normalized for w in (
                "total attendance", "how many total attendance", "attendance count", "total records"
            )):
                summary_result = attendance_tool(
                    employee_id=employee_id,
                    month=filters.get("month"),
                    year=filters.get("year")
                )
                summary = summary_result.get("summary", {})
                records = summary_result.get("records", [])
                return self._result("get_attendance_summary", {
                    "query_intent": "total_attendance",
                    "period": summary.get("month"),
                    "total_records": summary.get("total_records", len(records)),
                    "present_days": summary.get("present", 0),
                    "half_days": summary.get("half_day", 0),
                    "absent_days": summary.get("absent", 0),
                    "total_worked_hours": summary.get("total_worked_hours", 0),
                    "remaining_worked_minutes": summary.get("remaining_worked_minutes", 0),
                })

            # 8d. PRESENT / ABSENT DAYS COUNT
            if any(w in normalized for w in ("total present", "present days", "total present days", "absent days", "total absent")):
                summary_result = attendance_tool(
                    employee_id=employee_id,
                    month=filters.get("month"),
                    year=filters.get("year")
                )
                summary = summary_result.get("summary", {})
                return self._result("get_attendance_summary", {
                    "query_intent": "presence_summary",
                    "period": summary.get("month"),
                    "present_days": summary.get("present", 0),
                    "half_days": summary.get("half_day", 0),
                    "absent_days": summary.get("absent", 0),
                })

            # 8e. TOTAL WORKED HOURS (Month or General)
            if any(w in normalized for w in ("total hours", "total working hours", "total hour", "hours worked")):
                summary_result = attendance_tool(
                    employee_id=employee_id,
                    month=filters.get("month"),
                    year=filters.get("year")
                )
                summary = summary_result.get("summary", {})
                return self._result("get_attendance_summary", {
                    "query_intent": "total_hours",
                    "period": summary.get("month"),
                    "total_worked_hours": summary.get("total_worked_hours", 0),
                    "remaining_worked_minutes": summary.get("remaining_worked_minutes", 0),
                    "total_worked_minutes": summary.get("total_worked_minutes", 0),
                })

            # 8f. SHOW ATTENDANCE / MONTH ATTENDANCE OVERVIEW
            month_filter = filters.get("month")
            year_filter = filters.get("year") or (latest_year if month_filter else None)
            if month_filter:
                ctx["last_month"] = month_filter
                ctx["last_year"] = year_filter
                summary_result = attendance_tool(employee_id=employee_id, month=month_filter, year=year_filter)
                q_intent = "month_attendance"
            else:
                summary_result = attendance_tool(employee_id=employee_id)
                q_intent = "show_attendance"

            summary = summary_result.get("summary", {})
            records = summary_result.get("records", [])
            return self._result("get_attendance", {
                "query_intent": q_intent,
                "summary": {
                    "period": summary.get("month"),
                    "total_records": summary.get("total_records", len(records)),
                    "present_days": summary.get("present", 0),
                    "half_days": summary.get("half_day", 0),
                    "absent_days": summary.get("absent", 0),
                    "total_worked_hours": summary.get("total_worked_hours", 0),
                    "remaining_worked_minutes": summary.get("remaining_worked_minutes", 0),
                },
                "recent_records": records[:5],
                "records": records[:5],
            })

        return None

    def _latest_year(self, employee_id):
        frame = self.data.get_attendance(employee_id)
        if frame.empty:
            return datetime.now(INDIA_TIMEZONE).year
        years = frame["dateKey"].astype(str).str[:4]
        valid_years = [int(y) for y in years if y.isdigit()]
        return max(valid_years) if valid_years else datetime.now(INDIA_TIMEZONE).year

    @staticmethod
    def format_result(result, query):
        """Format verified structured data into an exact, query-specific natural response."""
        def label(value):
            return re.sub(r"(?<!^)([A-Z])", r" \1", value).replace("_", " ").title()

        if not result.get("success"):
            return result.get("message", "The requested data is unavailable.")

        data = result.get("data", {})
        tool_used = result.get("tool_used", "")
        q_intent = data.get("query_intent", "")

        # 1. Leave Balance
        if tool_used == "get_leave_balance":
            leave_types = data.get("leave_types", [])
            total_rem = data.get("total_remaining", data.get("remaining_leaves", 0))
            total_alloc = data.get("total_allocated", data.get("allocated_leaves", 0))
            total_used = data.get("total_used", data.get("used_leaves", 0))

            lines = [
                f"You currently have a total of **{total_rem} remaining leaves** out of {total_alloc} allocated days ({total_used} used). Here is your breakdown:\n"
            ]
            if leave_types:
                for lt in leave_types:
                    name = lt.get("name", "Leave")
                    code = f" ({lt['code']})" if lt.get("code") else ""
                    lines.append(f"- **{name}{code}:** {lt.get('remaining', 0)} remaining ({lt.get('used', 0)} used out of {lt.get('allocated', 0)} allocated)")
                lines.append("")
            lines.append(f"**Overall Balance:** {total_alloc} allocated, {total_used} used, **{total_rem} remaining**.\n\nPlease let me know if you need help applying for leave!")
            return "\n".join(lines)

        # 2. Leave Types / Policy
        if tool_used == "get_leave_types":
            types = data.get("leave_types", [])
            if not types:
                return "No leave types found."
            lines = ["Here are the available company leave policies:\n"]
            for lt in types:
                name = lt.get("name")
                alloc = lt.get("allocated_per_year", lt.get("daysPerYear", 0))
                paid = "Paid" if lt.get("is_paid") else "Unpaid"
                lines.append(f"- **{name}:** {alloc} days per year ({paid})")
            return "\n".join(lines)

        # 3. Leave Requests
        if tool_used == "get_leave_requests":
            reqs = data.get("leave_requests", [])
            if not reqs:
                return "You have no leave requests on record."
            lines = ["Here are your recent leave applications:\n"]
            for r in reqs:
                s = r.get("status", "Pending")
                f = r.get("from_date", "")
                t = r.get("to_date", "")
                days = r.get("days", 1)
                lines.append(f"- **{f} to {t}:** {days} day(s) - Status: **{s}**")
            return "\n".join(lines)

        # 4. Holidays
        if tool_used == "get_holidays":
            holidays = data.get("holidays", [])
            if not holidays:
                return "No holidays found for the specified period."
            lines = ["Here are the company holidays:\n"]
            for h in holidays:
                lines.append(f"- **{h.get('date')}:** {h.get('name')} ({h.get('type', 'Holiday')})")
            return "\n".join(lines)

        # 5. Shift
        if tool_used == "get_employee_shift":
            name = data.get("name", "Standard Shift")
            start = data.get("start_time", "")
            end = data.get("end_time", "")
            days = data.get("working_days", "")
            time_str = f" from **{start}** to **{end}**" if start and end else ""
            days_str = f" on {days}" if days else ""
            return f"You are currently assigned to the **{name}**{time_str}{days_str}."

        # 6. Branch
        if tool_used == "get_employee_branch":
            name = data.get("name", "")
            city = data.get("city", "")
            loc = f" in **{city}**" if city else ""
            return f"Your registered office branch is **{name}**{loc}."

        # 7. Designation
        if tool_used == "get_employee_designation":
            name = data.get("name", "")
            return f"Your current designation is **{name}**."

        # 8. Employee Profile
        if tool_used == "get_employee":
            name = data.get("name", "")
            des = data.get("designation", "")
            branch = data.get("branch", "")
            shift = data.get("shift", "")
            joining = data.get("joining_date", "")
            status = data.get("employment_status", "")
            lines = [f"Here are your employee details:"]
            if name:
                lines.append(f"- **Name:** {name}")
            if des:
                lines.append(f"- **Designation:** {des}")
            if branch:
                lines.append(f"- **Branch:** {branch}")
            if shift:
                lines.append(f"- **Shift:** {shift}")
            if joining:
                lines.append(f"- **Date of Joining:** {joining}")
            if status:
                lines.append(f"- **Employment Status:** {status}")
            return "\n".join(lines)

        # 9. Attendance Queries
        if tool_used in ("get_attendance", "get_attendance_summary"):
            record = data.get("record")
            date = data.get("date")

            # Check-in time query
            if q_intent == "check_in":
                if record and record.get("check_in"):
                    return f"On {date}, your check-in time was **{record['check_in']}**."
                return f"No check-in record is available for {date}."

            # Check-out time query
            if q_intent == "check_out":
                if record and record.get("check_out"):
                    return f"On {date}, your check-out time was **{record['check_out']}**."
                return f"No check-out record is available for {date}."

            # Worked hours on specific date
            if q_intent == "worked_hours":
                if record and (record.get("worked_hours") is not None or record.get("worked_minutes") is not None):
                    h = record.get("worked_hours", 0)
                    m = record.get("worked_minutes", 0)
                    return f"On {date}, you worked **{h} hour(s) and {m} minute(s)**."
                return f"No working hours record is available for {date}."

            # Presence query on specific date
            if q_intent == "presence":
                if record:
                    status = record.get("status", "Present")
                    cin = record.get("check_in")
                    cout = record.get("check_out")
                    h = record.get("worked_hours", 0)
                    m = record.get("worked_minutes", 0)
                    details = []
                    if cin:
                        details.append(f"check-in at **{cin}**")
                    if cout:
                        details.append(f"check-out at **{cout}**")
                    if h or m:
                        details.append(f"worked **{h}h {m}m**")
                    extra = f" ({', '.join(details)})" if details else ""
                    return f"On {date}, you were recorded as **{status}**{extra}."
                return f"No attendance record is available for {date}."

            # Specific date attendance overview
            if q_intent == "date_attendance":
                if record:
                    status = record.get("status", "Present")
                    cin = record.get("check_in") or "Not recorded"
                    cout = record.get("check_out") or "Not recorded"
                    h = record.get("worked_hours", 0)
                    m = record.get("worked_minutes", 0)
                    return (
                        f"Here is your attendance details for **{date}**:\n"
                        f"- **Status:** {status}\n"
                        f"- **Check-in:** {cin}\n"
                        f"- **Check-out:** {cout}\n"
                        f"- **Working Hours:** {h} hour(s) and {m} minute(s)"
                    )
                return f"No attendance record is available for {date}."

            # Total attendance count
            if q_intent == "total_attendance":
                period = data.get("period", "the period")
                total = data.get("total_records", 0)
                pres = data.get("present_days", 0)
                half = data.get("half_days", 0)
                absent = data.get("absent_days", 0)
                h = data.get("total_worked_hours", 0)
                m = data.get("remaining_worked_minutes", 0)
                return (
                    f"Here is your total attendance summary for **{period}**:\n"
                    f"- **Total Attendance Logged:** {total} day(s)\n"
                    f"- **Present Days:** {pres} day(s)\n"
                    f"- **Half Days:** {half} day(s)\n"
                    f"- **Absent Days:** {absent} day(s)\n"
                    f"- **Total Working Time:** {h} hour(s) and {m} minute(s)"
                )

            # Total hours query
            if q_intent == "total_hours":
                period = data.get("period", "the period")
                h = data.get("total_worked_hours", 0)
                m = data.get("remaining_worked_minutes", 0)
                return f"Your total working time for **{period}** is **{h} hour(s) and {m} minute(s)**."

            # General show attendance or month attendance overview
            summary = data.get("summary")
            recent = data.get("recent_records", [])
            if summary:
                period = summary.get("period", "the current period")
                lines = [
                    f"Here is your attendance summary for **{period}**:\n",
                    f"- **Present:** {summary.get('present_days', 0)} day(s)",
                    f"- **Half-day:** {summary.get('half_days', 0)} day(s)",
                    f"- **Absent:** {summary.get('absent_days', 0)} day(s)",
                    f"- **Total Records Logged:** {summary.get('total_records', len(recent))} day(s)",
                ]
                if summary.get("total_worked_hours") is not None:
                    lines.append(f"- **Total Working Time:** {summary.get('total_worked_hours', 0)} hour(s) and {summary.get('remaining_worked_minutes', 0)} minute(s)")

                if recent:
                    lines.append("\n**Recent Attendance Records:**\n")
                    for r in recent:
                        d = r.get("date", "Unknown")
                        status = r.get("status", "Present")
                        cin = r.get("check_in")
                        cout = r.get("check_out")
                        parts = [f"**Status:** {status}"]
                        if cin:
                            parts.append(f"**Check-in:** {cin}")
                        if cout:
                            parts.append(f"**Check-out:** {cout}")
                        if r.get("worked_minutes"):
                            parts.append(f"**Worked:** {r.get('worked_minutes')} min")
                        lines.append(f"- **{d}:** " + ", ".join(parts))
                lines.append("\nLet me know if you would like details for any specific date!")
                return "\n".join(lines)

        return result.get("message", "Data retrieved successfully.")

    @staticmethod
    def _missing(kind, filters=None):
        suffix = f" for {filters}" if filters else ""
        if isinstance(filters, str):
            return {"success": False, "message": filters}
        return {"success": False, "message": f"No {kind} data is available{suffix}."}

    @staticmethod
    def _result(tool, data):
        return {
            "success": True,
            "message": "Verified employee data is available.",
            "tool_used": tool,
            "data": data,
        }
