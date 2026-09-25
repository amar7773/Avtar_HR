"""Deterministic routing for exact employee data queries.

This layer deliberately runs before the LLM.  It prevents a generative model
from guessing values and keeps the payload sent to the model small.
"""
from datetime import datetime
import re

from app.Services.Data_services import DataService
from app.Tools.employee_tools import (
    format_india_datetime,
    get_attendance as attendance_tool,
)


MONTHS = {
    name: number for number, name in enumerate(
        ("january", "february", "march", "april", "may", "june",
         "july", "august", "september", "october", "november", "december"),
        1,
    )
}
MONTHS.update({name[:3]: number for name, number in list(MONTHS.items())})
HINDI_MONTHS = {"जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9,
                "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12}


class StructuredQueryRouter:
    """Parse and answer supported, employee-scoped questions without an LLM."""

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

    @staticmethod
    def _date_filters(query):
        q = query.casefold()
        today = datetime.now().date()
        if "today" in q or "आज" in q:
            return {"date": today.isoformat()}
        if "yesterday" in q or "कल" in q:
            return {"date": (today.fromordinal(today.toordinal() - 1)).isoformat()}
        match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", q)
        if match:
            return {"date": f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"}
        day_month = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?[\s/-]+"
            r"(january|february|march|april|may|june|july|august|"
            r"september|october|november|december|jan|feb|mar|apr|"
            r"jun|jul|aug|sep|sept|oct|nov|dec)\b",
            q,
        )
        if day_month:
            month_name = day_month.group(2)
            month = MONTHS.get(month_name, MONTHS.get(month_name[:3]))
            year = re.search(r"\b(20\d{2})\b", q)
            return {
                "day": int(day_month.group(1)),
                "month": month,
                "year": int(year.group(1)) if year else None,
            }
        for name, month in {**MONTHS, **HINDI_MONTHS}.items():
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", q):
                year = re.search(r"\b(20\d{2})\b", q)
                return {"month": month, "year": int(year.group(1)) if year else None}
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

    def route(self, query, employee_id):
        q = query.casefold()
        personal = any(word in q for word in (
            "my", "me", "i", "mera", "meri", "mere", "main", "mai",
            "मेरा", "मेरी", "मेरे", "मुझे", "अपना", "अपनी"
        ))
        if not employee_id or not personal and not any(
            word in q for word in ("attendance", "salary", "वेतन", "leave", "छुट्टी", "project", "profile", "experience", "designation", "branch", "shift", "joining")
        ):
            if any(word in q for word in ("available leave", "leaves available", "leaves are available", "leave type", "leave policy", "छुट्टी के प्रकार", "छुट्टी नीति")):
                pass
            else:
                return None
        if any(word in q for word in (
            "attendance", "check in", "check-in", "check out", "check-out",
            "उपस्थिति", "हाजिरी", "working hours", "working time",
            "total hours", "total minutes", "lifeline"
        )):
            kind = "attendance"
        elif any(word in q for word in ("leave type", "leave policy", "available leave", "leaves available", "leaves are available", "छुट्टी के प्रकार", "छुट्टी नीति")):
            kind = "leave_types"
        elif any(word in q for word in ("salary", "वेतन", "pay", "payslip")):
            kind = "salary"
        elif any(word in q for word in (
            "leave request", "leave requests", "leave history", "my leave",
            "my leaves", "show my leaves", "छुट्टी आवेदन", "मेरी छुट्टी"
        )):
            kind = "leave"
        elif any(word in q for word in ("project", "परियोजना")):
            kind = "projects"
        elif any(word in q for word in ("experience", "अनुभव", "profile", "प्रोफाइल", "designation", "branch", "shift", "joining")):
            kind = "profile"
        else:
            return None
        if kind == "leave_types":
            frame = self.data.get_leave_types()
            fields = ("name", "code", "daysPerYear", "isPaid", "allowHalfDay", "requiresApproval")
            records = [{field: (None if row[field] != row[field] else row[field])
                        for field in fields if field in row} for _, row in frame.iterrows()]
            if not records:
                return self._missing("leave types")
            return self._result("get_leave_types", {"records": records})
        if kind == "profile":
            frame = self.data.get_employee(employee_id)
            if frame.empty:
                return self._missing("profile")
            row = frame.iloc[0]
            profile = {"employee_id": str(row.get("employeeId")),
                "name": f"{row.get('firstName', '')} {row.get('lastName', '')}".strip(),
                "joining_date": row.get("dateOfJoining"), "job_type": row.get("jobType"),
                "employment_status": row.get("employmentStatus"), "status": row.get("status")}
            if "complete" in q or "all details" in q or "full" in q:
                profile.update({
                    "management_level": row.get("managementLevel"),
                })
                related = self.data.get_employee_designation(employee_id)
                if not related.empty:
                    profile["designation"] = related.iloc[0].get("name")
                related = self.data.get_employee_branch(employee_id)
                if not related.empty:
                    profile["branch"] = related.iloc[0].get("name")
                related = self.data.get_employee_shift(employee_id)
                if not related.empty:
                    profile["shift"] = related.iloc[0].get("shiftName")
            if "designation" in q:
                related = self.data.get_employee_designation(employee_id)
                if not related.empty:
                    profile["designation"] = related.iloc[0].get("name")
            if "branch" in q:
                related = self.data.get_employee_branch(employee_id)
                if not related.empty:
                    profile["branch"] = related.iloc[0].get("name")
            if "shift" in q:
                related = self.data.get_employee_shift(employee_id)
                if not related.empty:
                    profile["shift"] = related.iloc[0].get("shiftName")
            requested = set(profile) if (
                "complete" in q or "all details" in q or "full" in q
            ) else set()
            for key in ("joining_date", "job_type", "employment_status",
                        "status", "designation", "branch", "shift"):
                if key.replace("_", " ") in q or key in q:
                    requested.add(key)
            if not requested:
                requested = {"employee_id", "name"}
            if "joining" in q or "experience" in q:
                requested.add("joining_date")
            if "job" in q:
                requested.add("job_type")
            if "status" in q:
                requested.update(("employment_status", "status"))
            for key in ("designation", "branch", "shift"):
                if key in profile and key in q:
                    requested.add(key)
            return self._result("get_employee", {key: profile[key] for key in requested})
        filters = self._date_filters(query)
        if kind == "attendance" and any(word in q for word in (
            "remaining", "left", "bachi", "बची", "बचती"
        )) and "lifeline" in q:
            return self._missing(
                "remaining lifeline balance",
                "No lifeline limit or remaining-balance field exists in the attendance data."
            )
        if kind == "attendance" and any(word in q for word in (
            "total hours", "total hour", "working hours", "working time",
            "hours i work", "hours worked", "total minutes", "कितने घंटे"
        )):
            summary_result = attendance_tool(
                employee_id=employee_id,
                **filters
            )
            if not summary_result.get("records"):
                return self._missing("attendance", filters)
            summary = summary_result.get("summary", {})
            return self._result("get_attendance_summary", {
                "total_worked_hours": summary.get("total_worked_hours", 0),
                "total_worked_minutes": summary.get("total_worked_minutes", 0),
                "remaining_minutes": summary.get("remaining_worked_minutes", 0),
                "period": summary.get("month"),
            })
        if kind == "attendance" and any(word in q for word in (
            "total attendance", "attendance count"
        )):
            summary_result = attendance_tool(
                employee_id=employee_id,
                **filters
            )
            if not summary_result.get("records"):
                return self._missing("attendance", filters)
            summary = summary_result.get("summary", {})
            return self._result("get_attendance_summary", {
                "total_attendance_days": summary.get("total_records", 0),
                "period": summary.get("month"),
            })
        if kind == "attendance" and any(word in q for word in (
            "total present",
            "present days", "total present days"
        )):
            summary_result = attendance_tool(
                employee_id=employee_id,
                **filters
            )
            if not summary_result.get("records"):
                return self._missing("attendance", filters)
            summary = summary_result.get("summary", {})
            return self._result("get_attendance_summary", {
                "present_days": summary.get("present", 0),
                "absent_days": summary.get("absent", 0),
                "half_days": summary.get("half_day", 0),
                "period": summary.get("month"),
            })
        if kind == "attendance" and "lifeline" in q:
            summary_result = attendance_tool(
                employee_id=employee_id,
                **filters
            )
            if not summary_result.get("records"):
                return self._missing("attendance", filters)
            summary = summary_result.get("summary", {})
            requested = {}
            if "late check" in q or "late_check_in" in q:
                requested["late_check_in_lifelines"] = summary.get(
                    "late_check_in_lifelines", 0
                )
            if "early checkout" in q or "check out" in q or "checkout" in q:
                requested["early_checkout_lifelines"] = summary.get(
                    "late_check_out_lifelines", 0
                )
            if requested:
                requested["period"] = summary.get("month")
                return self._result("get_attendance_summary", requested)
        if kind == "leave":
            status = next((s for s in ("approved", "rejected", "pending", "cancelled")
                           if s in q), None)
            frame = self.data.get_leave_requests(employee_id, status=status)
            if filters.get("date") and "fromDate" in frame:
                frame = frame[frame["fromDate"].astype(str).str.startswith(filters["date"])]
            elif filters.get("month") and filters.get("year") and "fromDate" in frame:
                prefix = f"{filters['year']}-{filters['month']:02d}"
                frame = frame[frame["fromDate"].astype(str).str.startswith(prefix)]
            if frame.empty:
                return self._missing(kind, {"status": status} if status else None)
            fields = self._fields(query, kind)
            records = [{field: (None if row[source] != row[source] else row[source])
                        for field in fields
                        for source in self.DATA_FIELDS[kind][field] if source in row}
                       for _, row in frame.iterrows()]
            return self._result("get_leave_requests", {"records": records})
        if kind == "attendance":
            if filters.get("day") and filters.get("month") and not filters.get("year"):
                all_rows = self.data.get_attendance(employee_id)
                years = [
                    str(value)[:4] for value in all_rows.get("dateKey", [])
                    if str(value)[:4].isdigit()
                ]
                filters["year"] = max(years) if years else datetime.now().year
                filters["date"] = (
                    f"{filters['year']}-{filters['month']:02d}-{filters['day']:02d}"
                )
                filters.pop("day", None)
            elif filters.get("month") and not filters.get("year"):
                all_rows = self.data.get_attendance(employee_id)
                years = [
                    str(value)[:4] for value in all_rows.get("dateKey", [])
                    if str(value)[:4].isdigit()
                ]
                filters["year"] = max(years) if years else datetime.now().year
            frame = self.data.get_attendance(employee_id, **filters)
        elif kind == "salary":
            frame = self.data.get_salary(employee_id, month=filters.get("month"))
        else:
            status = next((s for s in ("completed", "in progress", "active", "pending")
                           if s in q), None)
            frame = self.data.get_projects(employee_id, status=status)
        if frame.empty:
            return self._missing(kind, filters)
        fields = self._fields(query, kind)
        records = []
        for _, row in frame.iterrows():
            record = {}
            if kind == "attendance" and len(frame) > 1:
                record["date"] = row.get("dateKey")
            for field in fields:
                source = next((column for column in self.DATA_FIELDS[kind][field]
                               if column in row), None)
                if source:
                    value = row[source]
                    record[field] = None if value != value else value
            records.append(record)
        return self._result(f"get_{kind}", {"records": records, "filters": filters})

    @staticmethod
    def format_result(result, query):
        """Turn already-filtered structured data into a concise answer."""
        def label(value):
            return re.sub(r"(?<!^)([A-Z])", r" \1", value).replace("_", " ").title()

        if not result.get("success"):
            return result.get("message", "The requested data is unavailable.")
        data = result.get("data", {})
        records = data.get("records", [])
        if not records and data:
            return "\n".join(
                f"**{label(key)}:** {value}"
                for key, value in data.items()
                if value is not None and str(value).lower() != "nan"
            ) or result.get("message", "No matching data was found.")
        if not records:
            return result.get("message", "No matching data was found.")
        query_lower = query.casefold()
        if len(records) == 1 and "attendance" in result.get("tool_used", ""):
            record = records[0]
            date = record.get("date") or record.get("dateKey", "")
            if not date:
                date = data.get("filters", {}).get("date", "")
            if "check out" in query_lower or "check-out" in query_lower:
                value = record.get("check_out")
                if value:
                    value = format_india_datetime(value)
                    return f"Your check-out time on {date} was **{value}**."
                return f"No check-out record is available for {date}."
            if "check in" in query_lower or "check-in" in query_lower:
                value = record.get("check_in")
                if value:
                    value = format_india_datetime(value)
                    return f"Your check-in time on {date} was **{value}**."
                return f"No check-in record is available for {date}."
        if len(records) == 1:
            values = records[0]
            return "\n".join(
                f"**{label(key)}:** {value}"
                for key, value in values.items()
                if value is not None
            )
        return "\n".join(
            f"- " + ", ".join(
                f"**{label(key)}:** {(
                    format_india_datetime(value)
                    if key in ('check_in', 'check_out') and value
                    else value
                )}"
                for key, value in record.items()
                if value is not None
            )
            for record in records
        )

    @staticmethod
    def _missing(kind, filters=None):
        suffix = f" for {filters}" if filters else ""
        if isinstance(filters, str):
            return {"success": False, "message": filters}
        return {"success": False, "message": f"No {kind} data is available{suffix}."}

    @staticmethod
    def _result(tool, data):
        return {"success": True, "message": "Exact data retrieved.", "tool_used": tool, "data": data}
