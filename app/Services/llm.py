import os
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

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


load_dotenv()


class LLMServices:

    INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

    def __init__(self):

        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )

        self.model = "gemini-3.5-flash-lite"

        self.tools = [
            types.Tool(
                function_declarations=[

                    types.FunctionDeclaration(
                        name="get_employee",
                        description=(
                            "Get employee profile information including "
                            "name, employee ID, designation, branch, shift "
                            "and employment status."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Employee ID such as EMP-0013."
                                    )
                                )
                            },
                            required=["employee_id"]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_attendance",
                        description=(
                            "Get attendance records for an employee. "
                            "Can be filtered by specific date, month or year."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Employee ID such as EMP-0013."
                                    )
                                ),
                                "date": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Specific date in YYYY-MM-DD format."
                                    ),
                                    nullable=True
                                ),
                                "month": types.Schema(
                                    type="INTEGER",
                                    description="Month number from 1 to 12.",
                                    nullable=True
                                ),
                                "year": types.Schema(
                                    type="INTEGER",
                                    description="Year such as 2026.",
                                    nullable=True
                                )
                            },
                            required=[
                                "employee_id",
                                "date",
                                "month",
                                "year"
                            ]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_leave_requests",
                        description=(
                            "Get valid leave requests for an employee. "
                            "Can filter by leave status such as approved, "
                            "rejected or pending."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Employee ID such as EMP-0013."
                                    )
                                ),
                                "status": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Leave status such as approved, "
                                        "rejected or pending."
                                    ),
                                    nullable=True
                                )
                            },
                            required=[
                                "employee_id",
                                "status"
                            ]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_leave_types",
                        description=(
                            "Get active company leave types and "
                            "their leave policies."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={}
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_holidays",
                        description=(
                            "Get active company holidays. "
                            "Can be filtered by year and month."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "year": types.Schema(
                                    type="INTEGER",
                                    description="Year such as 2026.",
                                    nullable=True
                                ),
                                "month": types.Schema(
                                    type="INTEGER",
                                    description="Month number from 1 to 12.",
                                    nullable=True
                                )
                            },
                            required=[
                                "year",
                                "month"
                            ]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_employee_shift",
                        description=(
                            "Get the shift assigned to an employee "
                            "including start time, end time and "
                            "working days."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Employee ID such as EMP-0013."
                                    )
                                )
                            },
                            required=["employee_id"]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_employee_branch",
                        description=(
                            "Get the branch assigned to an employee."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Employee ID such as EMP-0013."
                                    )
                                )
                            },
                            required=["employee_id"]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_employee_designation",
                        description=(
                            "Get the designation assigned to an employee."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Employee ID such as EMP-0013."
                                    )
                                )
                            },
                            required=["employee_id"]
                        )
                    )

                ]
            )
        ]

    @staticmethod
    def _response_text(response):
        parts = getattr(
            getattr(response, "candidates", [None])[0],
            "content",
            None
        )
        parts = getattr(parts, "parts", []) if parts else []
        text_parts = [
            part.text for part in parts
            if getattr(part, "text", None)
        ]
        return "\n".join(text_parts).strip()

    @staticmethod
    def _function_call(response):
        parts = getattr(
            getattr(response, "candidates", [None])[0],
            "content",
            None
        )
        parts = getattr(parts, "parts", []) if parts else []
        for part in parts:
            function_call = getattr(part, "function_call", None)
            if function_call:
                return function_call
        return None

    def _run_tool(self, function_name, arguments, employee_id=None):
        if employee_id and function_name in {
            "get_employee",
            "get_attendance",
            "get_leave_requests",
            "get_employee_shift",
            "get_employee_branch",
            "get_employee_designation"
        }:
            arguments["employee_id"] = employee_id

        if function_name == "get_employee":
            return get_employee(employee_id=arguments["employee_id"])
        if function_name == "get_attendance":
            return get_attendance(
                employee_id=arguments["employee_id"],
                date=arguments.get("date"),
                month=arguments.get("month"),
                year=arguments.get("year")
            )
        if function_name == "get_leave_requests":
            return get_leave_requests(
                employee_id=arguments["employee_id"],
                status=arguments.get("status")
            )
        if function_name == "get_leave_types":
            return get_leave_types()
        if function_name == "get_holidays":
            return get_holidays(
                year=arguments.get("year"),
                month=arguments.get("month")
            )
        if function_name == "get_employee_shift":
            return get_employee_shift(employee_id=arguments["employee_id"])
        if function_name == "get_employee_branch":
            return get_employee_branch(employee_id=arguments["employee_id"])
        if function_name == "get_employee_designation":
            return get_employee_designation(
                employee_id=arguments["employee_id"]
            )
        return None

    @staticmethod
    def _format_attendance_response(result, query=""):
        records = result.get("records", [])
        summary = result.get("summary", {})
        if not records:
            return result.get(
                "message",
                "No attendance records found."
            )

        query_lower = query.lower()
        asks_absent = "absent" in query_lower or "अबसेंट" in query_lower
        asks_lifeline = (
            "lifeline" in query_lower
            or "early checkout" in query_lower
            or "late checkout" in query_lower
            or "late check-in" in query_lower
            or "late check in" in query_lower
        )
        asks_worked_total = (
            ("hour" in query_lower or "hours" in query_lower)
            and ("total" in query_lower or "worked" in query_lower)
        ) or (
            "working hours" in query_lower
            or "working time" in query_lower
            or "total minutes" in query_lower
            or "कितने घंटे" in query_lower
            or "कितने घंटे और मिनट" in query_lower
        )
        asks_half_day = (
            "half day" in query_lower
            or "half-day" in query_lower
            or "halfday" in query_lower
            or "हाफ डे" in query_lower
        )
        asks_present = (
            "total present" in query_lower
            or "present days" in query_lower
            or "present date" in query_lower
            or "total parsent" in query_lower
            or "parsent date" in query_lower
            or "पर्सेंट" in query_lower
        )
        if asks_worked_total and not asks_lifeline and not asks_absent:
            return (
                f"For {summary.get('month', 'the selected month')}, "
                f"your total working time was "
                f"{summary.get('total_worked_hours', 0)} hour(s) and "
                f"{summary.get('remaining_worked_minutes', 0)} minute(s)."
            )

        if asks_half_day and not asks_lifeline and not asks_absent:
            dates = summary.get("half_day_dates", [])
            lines = [
                "### Half-day attendance",
                "",
                f"You had **{summary.get('half_day', 0)} half-day(s)** "
                f"in {summary.get('month', 'the selected month')}:",
                ""
            ]
            lines.extend(
                f"- **{LLMServices._format_summary_date(date)}:** "
                "Status: Half Day."
                for date in dates
            )
            return "\n".join(lines)

        if asks_present and not asks_lifeline and not asks_absent:
            dates = summary.get("present_dates", [])
            lines = [
                "### Present attendance",
                "",
                f"You were present on **{summary.get('present', 0)} day(s)** "
                f"in {summary.get('month', 'the selected month')}:",
                ""
            ]
            lines.extend(
                f"- **{LLMServices._format_summary_date(date)}:** "
                "Status: Present."
                for date in dates
            )
            return "\n".join(lines)

        if asks_absent and not asks_lifeline:
            absent_dates = summary.get("absent_dates", [])
            date_text = ", ".join(absent_dates) or "none"
            return (
                f"For {summary.get('month', 'the selected month')}, "
                f"you were absent on {summary.get('absent', 0)} day(s). "
                f"Present on {summary.get('present', 0)} day(s), "
                f"and worked for "
                f"{summary.get('total_worked_hours', 0)} hour(s) "
                f"and {summary.get('remaining_worked_minutes', 0)} "
                f"minute(s) in total. "
                f"Absent date(s): {date_text}."
            )

        if asks_lifeline and not asks_absent:
            late_in_dates = ", ".join(
                summary.get("late_check_in_dates", [])
            ) or "none"
            early_out_dates = ", ".join(
                summary.get("early_checkout_dates", [])
            ) or "none"
            return (
                f"For {summary.get('month', 'the selected month')}, "
                f"late check-in lifeline was used "
                f"{summary.get('late_check_in_lifelines', 0)} time(s) "
                f"on: {late_in_dates}. "
                f"Early check-out lifeline was used "
                f"{summary.get('late_check_out_lifelines', 0)} time(s) "
                f"on: {early_out_dates}."
            )

        lines = ["Here are your most recent attendance records:\n"]
        if summary:
            month = summary.get("month", "")
            try:
                month = datetime.strptime(
                    f"{month}-01",
                    "%Y-%m-%d"
                ).strftime("%B %Y")
            except (TypeError, ValueError):
                pass
            lines.append(
                f"For {month}: you were absent on "
                f"{summary.get('absent', 0)} day(s). "
                f"Late check-in lifeline used: "
                f"{summary.get('late_check_in_lifelines', 0)} time(s). "
                f"Late check-out lifeline used: "
                f"{summary.get('late_check_out_lifelines', 0)} time(s).\n"
            )
        for record in records:
            date = record.get("date", "Unknown date")
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d")
                date = (
                    f"{parsed_date.strftime('%B')} "
                    f"{parsed_date.day}, "
                    f"{parsed_date.year}"
                )
            except (TypeError, ValueError):
                pass

            details = [
                f"- **{date}:**",
                f"Status: {record.get('status') or 'Not available'}"
            ]
            if record.get("check_in"):
                details.append(
                    "Check-in at "
                    f"{LLMServices._attendance_time(record['check_in'])}"
                )
            if record.get("check_out"):
                details.append(
                    "Check-out at "
                    f"{LLMServices._attendance_time(record['check_out'])}"
                )
            if (
                record.get("check_out")
                and record.get("worked_minutes") is not None
            ):
                details.append(
                    f"Worked for {record['worked_minutes']} minutes"
                )
            if record.get("is_late"):
                details.append(
                    f"Late by {record.get('late_by_minutes', 0)} minutes"
                )
            lines.append(f"{details[0]} " + ", ".join(details[1:]) + ".")

        lines.append(
            "\nThese records are shown using your attendance data. "
            "Let me know if you would like to see a specific date or month."
        )

        return "\n".join(lines)

    @staticmethod
    def _attendance_time(value):
        try:
            return datetime.strptime(
                value,
                "%Y-%m-%d %I:%M %p IST"
            ).strftime("%I:%M %p IST")
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _format_summary_date(value):
        try:
            parsed_date = datetime.strptime(value, "%Y-%m-%d")
            return (
                f"{parsed_date.strftime('%B')} "
                f"{parsed_date.day}, "
                f"{parsed_date.year}"
            )
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _format_leave_types_response(result):
        leave_types = result.get("leave_types", [])
        if not leave_types:
            return "No active leave types are currently available."

        lines = [
            "### Available leave types",
            "",
            "Here are the active leave types and their policies:",
            ""
        ]
        for index, leave in enumerate(leave_types, start=1):
            lines.extend([
                f"{index}. **{leave.get('name', 'Unnamed leave')} "
                f"({leave.get('code', '')})**",
                f"   - **Days per year:** "
                f"{leave.get('days_per_year', 'Not available')}",
                f"   - **Paid:** "
                f"{'Yes' if leave.get('is_paid') else 'No'}",
                f"   - **Half-day allowed:** "
                f"{'Yes' if leave.get('allow_half_day') else 'No'}",
                f"   - **Carry forward:** "
                f"{'Yes' if leave.get('carry_forward') else 'No'}",
                f"   - **Requires approval:** "
                f"{'Yes' if leave.get('requires_approval') else 'No'}",
                ""
            ])
        return "\n".join(lines).rstrip()

    @staticmethod
    def _attendance_filters(query):
        query_lower = query.lower()
        today = datetime.now(
            LLMServices.INDIA_TIMEZONE
        ).date()

        if "yesterday" in query_lower or "कल" in query_lower:
            return {
                "date": (today - timedelta(days=1)).isoformat()
            }
        if "today" in query_lower or "आज" in query_lower:
            return {"date": today.isoformat()}

        iso_date = re.search(
            r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b",
            query_lower
        )
        if iso_date:
            year, month, day = iso_date.groups()
            return {
                "date": (
                    f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                )
            }

        month_names = {
            "january": 1, "february": 2, "march": 3,
            "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9,
            "october": 10, "november": 11, "december": 12
        }
        for month_name, month_number in month_names.items():
            if month_name in query_lower:
                year_match = re.search(r"\b(20\d{2})\b", query_lower)
                return {
                    "month": month_number,
                    "year": int(year_match.group(1))
                    if year_match else today.year
                }

        return {}


    def genreate_response(
        self,
        query,
        context=None,
        employee_id=None,
        user_query=None
    ):

        current_india_time = datetime.now(
            self.INDIA_TIMEZONE
        ).strftime("%Y-%m-%d %I:%M %p IST")
        prompt = f"""
You are an AI Employee Assistant.

Your job is to help employees with:

- Employee profile
- Attendance
- Leave requests
- Leave policies
- Company holidays
- Employee shift
- Employee branch
- Employee designation
- Company policies
- Company-related information
- General questions about the employee assistant

IMPORTANT RULES:

1. If the user asks for personal employee information,
   use the appropriate employee tool.

2. For attendance questions, use get_attendance.

3. For leave request questions, use get_leave_requests.

4. For leave policy questions, use get_leave_types.

5. For company holiday questions, use get_holidays.

6. For employee profile questions, use get_employee.

7. For shift-related questions, use get_employee_shift.

8. For branch-related questions, use get_employee_branch.

9. For designation-related questions, use get_employee_designation.

10. Use the provided company context when answering questions
    about company policies or company-specific information.

11. Do not invent company policies, rules, benefits,
    employee information or attendance information.

12. If the required company information is not available
    in the provided context or employee tools, clearly say
    that the information is not available.

13. Always use the employee_id provided by the application
    when accessing personal employee information.

14. Give clear, concise and natural answers.

15. Do not expose MongoDB IDs, internal database fields,
    organization IDs or other unnecessary technical fields
    to the employee.

16. When a tool returns records, use the returned values exactly.
    Do not change dates, times, status, worked minutes or totals.
    Attendance times are already converted to India Standard Time
    and must be shown as returned.

17. For ordinary general-knowledge questions that are not about
    employee or company data, answer directly from your general
    knowledge. Do not invent facts.

18. Use the current India date and time provided below when interpreting
    words such as today, yesterday, current, latest or now. Do not present
    an old office-holder, result, price, weather value or other time-sensitive
    fact as current. If a current fact cannot be verified from the available
    context, say that current live information is unavailable instead of
    guessing.

Company Context:
{context}

User Question:
{query}

Current date and time in India:
{current_india_time}
"""

        routing_query = user_query or query
        query_lower = routing_query.lower()
        asks_attendance_summary = (
            "attendance" in query_lower
            or "check in" in query_lower
            or "check-in" in query_lower
            or "check out" in query_lower
            or "check-out" in query_lower
            or "yesterday" in query_lower
            or "today" in query_lower
            or "कल" in query_lower
            or "आज" in query_lower
            or "absent" in query_lower
            or "lifeline" in query_lower
            or "early checkout" in query_lower
            or "late checkout" in query_lower
            or "late check-in" in query_lower
            or "late check in" in query_lower
            or "अबसेंट" in query_lower
            or "working hours" in query_lower
            or "working time" in query_lower
            or "total hours" in query_lower
            or "total minutes" in query_lower
            or "कितने घंटे" in query_lower
            or "half day" in query_lower
            or "half-day" in query_lower
            or "halfday" in query_lower
            or "हाफ डे" in query_lower
            or "total present" in query_lower
            or "present days" in query_lower
            or "present date" in query_lower
            or "total parsent" in query_lower
            or "पर्सेंट" in query_lower
        )
        asks_available_leaves = (
            ("leave" in query_lower or "leaves" in query_lower)
            and (
                "available" in query_lower
                or "policy" in query_lower
                or "policies" in query_lower
                or "types" in query_lower
            )
        )
        if asks_available_leaves:
            leave_result = get_leave_types()
            return {
                "type": "message",
                "response": self._format_leave_types_response(
                    leave_result
                ),
                "tool_used": "get_leave_types",
                "tool_result": leave_result
            }

        if asks_attendance_summary and employee_id:
            attendance_result = get_attendance(
                employee_id=employee_id,
                **self._attendance_filters(query)
            )
            return {
                "type": "message",
                "response": self._format_attendance_response(
                    attendance_result,
                    query=routing_query
                ),
                "tool_used": "get_attendance",
                "tool_result": attendance_result
            }

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=self.tools
            )
        )

        tool_used = None
        tool_result = None
        contents = [prompt]

        for _ in range(3):
            function_call = self._function_call(response)
            if not function_call:
                text = self._response_text(response)
                if text:
                    return {
                        "type": "message",
                        "response": text,
                        "tool_used": tool_used,
                        "tool_result": tool_result
                    }
                break

            function_name = function_call.name
            arguments = dict(function_call.args)
            result = self._run_tool(
                function_name,
                arguments,
                employee_id=employee_id
            )

            if result is None:
                break

            tool_used = function_name
            tool_result = result
            if function_name == "get_attendance":
                return {
                    "type": "message",
                    "response": self._format_attendance_response(
                        result,
                        query=routing_query
                    ),
                    "tool_used": tool_used,
                    "tool_result": tool_result
                }

            contents.extend([
                response.candidates[0].content,
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=function_name,
                            response=result
                        )
                    ]
                )
            ])
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(tools=self.tools)
            )

        fallback = (
            "I couldn't find reliable information to answer that question. "
            "Please ask about your employee data or company information."
        )
        return {
            "type": "message",
            "response": fallback,
            "tool_used": tool_used,
            "tool_result": tool_result
        }
