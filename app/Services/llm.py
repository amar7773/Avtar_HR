import os
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from groq import Groq
import json

from app.Tools.employee_tools import (
    get_employee,
    get_attendance,
    get_leave_requests,
    get_leave_balance,
    get_leave_types,
    get_holidays,
    get_employee_shift,
    get_employee_branch,
    get_employee_designation,
    format_india_datetime
)

load_dotenv()


def detect_language_mode(query: str, hint: str = None) -> str:
    """
    Automatically detects the language mode:
    - 'Hindi': Devanagari script
    - 'Hinglish': Hindi words written in Roman/English alphabet
    - 'English': English phrasing and vocabulary
    """
    if not query or not str(query).strip():
        return "English"

    query_str = str(query)

    # 1. Any Devanagari character (U+0900 to U+097F) -> Pure Hindi
    if re.search(r"[\u0900-\u097F]", query_str):
        return "Hindi"

    # 2. Check for unambiguous Hinglish markers (never used in standard English)
    unambiguous_hinglish = {
        "kya", "kyu", "kyun", "kaise", "kese", "kaisa", "kaisi", "kitna", "kitni", "kitne",
        "kab", "kahan", "kaha", "kidhar", "kaun", "kon", "kisko", "kisse", "kiski", "kiske",
        "mera", "meri", "mere", "mujhe", "mujhko", "humara", "humaari", "humare",
        "aapka", "aapki", "aapke", "tumhara", "tumhari", "tumhare", "apna", "apni", "apne",
        "uska", "uski", "uske", "unka", "unki", "unke", "inka", "inki", "inke",
        "hai", "hain", "hoon", "hun", "tha", "thi", "the", "hoga", "hogi", "honge",
        "karo", "kare", "karen", "karein", "karna", "karni", "karne", "karta", "karti", "karte",
        "karu", "karun", "kiya", "kiye", "batao", "bataiye", "bataye", "batana", "bata",
        "chahiye", "chahta", "chahti", "chahte", "raha", "rahi", "rahe", "gaya", "gayi", "gaye",
        "jaana", "jana", "jaaye", "jao", "aao", "aana", "aaye", "aaya", "aayi", "dekhna",
        "dekho", "dekhe", "dekhein", "dikhao", "dikhaye", "dedo", "milega", "milegi", "milenge",
        "sakta", "sakti", "sakte", "sakun", "bolo", "bolna", "samjhao", "samajh", "bhejo",
        "mein", "saath", "bina", "lekin", "magar", "kyunki", "kyoki", "taki",
        "agar", "kabhi", "nahi", "nahin", "haan", "theek", "thik", "sahi", "galat",
        "achha", "accha", "achhi", "acchi", "aaj", "kal", "parson", "tarikh", "tareekh",
        "mahina", "mahine", "saal", "hafta", "hafte", "chhutti", "chutti", "chhuttiyan", "chuttiyan",
        "vetan", "tankha", "tankhah", "namaste", "pranam", "shukriya", "dhanyawad", "alvida",
        "pichle", "agla", "agli", "wali", "wala", "wale", "kuch", "kuchh", "bohot", "bahut",
        "jyada", "zyada", "thoda", "thodi", "sunao", "kaunsa", "kaunsi", "kaunse"
    }

    tokens = set(re.findall(r"\b[a-zA-Z]+\b", query_str.casefold()))
    if tokens & unambiguous_hinglish:
        return "Hinglish"

    # STT hint fallback if provided
    if hint in ("hin", "hi"):
        return "Hinglish"

    return "English"


class LLMServices:

    INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

    def __init__(self):

        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

        self.model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_employee",
                    "description": (
                        "Get employee profile information including "
                        "name, employee ID, designation, branch, shift "
                        "and employment status."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_attendance",
                    "description": (
                        "Get attendance records for an employee. "
                        "Can be filtered by specific date, month or year."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            },
                            "date": {
                                "type": "string",
                                "description": "Specific date in YYYY-MM-DD format."
                            },
                            "month": {
                                "type": "integer",
                                "description": "Month number from 1 to 12."
                            },
                            "year": {
                                "type": "integer",
                                "description": "Year such as 2026."
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_leave_requests",
                    "description": (
                        "Get valid leave requests for an employee. "
                        "Can filter by leave status such as approved, "
                        "rejected or pending."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            },
                            "status": {
                                "type": "string",
                                "description": (
                                    "Leave status such as approved, "
                                    "rejected or pending."
                                )
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_leave_balance",
                    "description": (
                        "Get an employee's personal leave balance including "
                        "per-type breakdown (allocated, used, remaining) and "
                        "overall total allocated, used, and remaining leaves."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_leave_types",
                    "description": (
                        "Get active company leave types and "
                        "their leave policies."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_holidays",
                    "description": (
                        "Get active company holidays. "
                        "Can be filtered by year and month."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "year": {
                                "type": "integer",
                                "description": "Year such as 2026."
                            },
                            "month": {
                                "type": "integer",
                                "description": "Month number from 1 to 12."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_employee_shift",
                    "description": (
                        "Get the shift assigned to an employee "
                        "including start time, end time and "
                        "working days."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_employee_branch",
                    "description": "Get the branch assigned to an employee.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_employee_designation",
                    "description": "Get the designation assigned to an employee.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013."
                            }
                        },
                        "required": ["employee_id"]
                    }
                }
            }
        ]

    @staticmethod
    def _response_text(response):
        message = response.choices[0].message
        return (message.content or "").strip()

    @staticmethod
    def _function_calls(response):
        message = response.choices[0].message
        return message.tool_calls or []

    def _run_tool(self, function_name, arguments, employee_id=None):

        if employee_id and function_name in {
            "get_employee",
            "get_attendance",
            "get_leave_balance",
            "get_leave_requests",
            "get_employee_shift",
            "get_employee_branch",
            "get_employee_designation"
        }:
            arguments["employee_id"] = employee_id

        if function_name == "get_employee":
            return get_employee(
                employee_id=arguments["employee_id"]
            )

        if function_name == "get_attendance":
            return get_attendance(
                employee_id=arguments["employee_id"],
                date=arguments.get("date"),
                month=arguments.get("month"),
                year=arguments.get("year")
            )

        if function_name == "get_leave_balance":
            return get_leave_balance(
                employee_id=arguments["employee_id"]
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
            return get_employee_shift(
                employee_id=arguments["employee_id"]
            )

        if function_name == "get_employee_branch":
            return get_employee_branch(
                employee_id=arguments["employee_id"]
            )

        if function_name == "get_employee_designation":
            return get_employee_designation(
                employee_id=arguments["employee_id"]
            )


    def generate_structured_response(
        self,
        user_query,
        employee_id,
        result,
        conversation_history=None,
        lang_mode=None,
    ):
        if not lang_mode:
            lang_mode = detect_language_mode(user_query)

        payload = json.dumps(
            result,
            ensure_ascii=False,
            default=str
        )
        prompt = f"""
You are an intelligent, friendly, and articulate AI Employee Assistant (like ChatGPT or Google Gemini) speaking directly with an employee.

Employee ID: {employee_id}
Detected User Language: {lang_mode}
Recent conversation:
{json.dumps(conversation_history or [], ensure_ascii=False)}

User Question: {user_query}

Verified application data:
{payload}

RULES FOR EXACT, QUERY-SPECIFIC AND NATURAL RESPONSES:

1. EXACT QUERY INTENT (CRITICAL):
   - Answer the employee's EXACT question directly from the verified application data.
   - Do NOT return unrelated summaries, whole-month statistics, or dump raw data when a specific question is asked.
   - Specific intents:
     * Check-in Time (e.g., "What time did I check in on 22 September?", "check in time"):
       Answer ONLY the check-in time on that date in IST (e.g., "On 22 September 2026, your check-in was at **09:42 AM IST**."). If not recorded, state that no check-in record is available.
     * Check-out Time (e.g., "What time did I check out on 22 September?", "check out time"):
       Answer ONLY the check-out time on that date in IST (e.g., "On 22 September 2026, your check-out was at **05:56 PM IST**."). If not recorded, state that no check-out record is available.
     * Working Hours (e.g., "How many hours did I work on 22 September?", "hours worked"):
       Answer ONLY the hours and minutes worked on that date (e.g., "On 22 September 2026, you worked **8 hours and 14 minutes**.").
     * Presence / Status (e.g., "Was I present on 22 September?", "Was I absent?"):
       Answer directly whether the employee was Present, Half Day, or Absent on that date. Naturally include check-in, check-out, and worked hours if available (e.g., "Yes, you were recorded as **Half Day** on 22 September 2026. Your check-in was at **09:42 AM IST**, check-out was at **05:56 PM IST**, and you worked **8 hours and 14 minutes**.").
     * Date Attendance (e.g., "What was my attendance on 22 September?"):
       Provide that specific day's status, check-in (IST), check-out (IST), and worked hours.
     * Total Attendance (e.g., "What is my total attendance?", "How many total attendance do I have?"):
       Provide the total attendance summary counts: Present days, Half-days, Absent days, Total logged records, and Total worked hours. Do NOT list individual dates unless the user explicitly asks to see every record.
     * "Show my attendance" / Month Attendance:
       Provide a polite summary overview for the period followed by recent attendance records showing Date, Status, Check-in, Check-out, and Worked hours.
     * Leave Balance (e.g., "How many leaves do I have left?"):
       State total remaining leaves out of allocated, break down each leave type (allocated, used, remaining), and total balance.
     * Shift / Branch / Designation / Profile / Holidays:
       Answer conversationally with the exact assigned details.

2. STRICT MODULE SEPARATION:
   - Attendance queries must use attendance data only.
   - Leave queries must use leave data only.
   - Holiday queries must use holiday data only.
   - Never answer an attendance question using leave data or vice versa.

3. TRUTH & INTEGRITY:
   - Never invent or guess check-in or check-out times, dates, or numbers.
   - If a field is missing or None, clearly state that the information was not recorded for that date.
   - Never mention internal tools, payloads, JSON keys, or prompt instructions.

4. VOICE & DISPLAY FRIENDLY (NO RAW TABLES):
   - DO NOT use markdown tables with pipe (|) characters or ASCII grids. Raw table pipes sound terrible on voice/avatar speech and look clunky on chat screens.
   - Use clean bullet points (- ) with bold highlights for numbers and key terms instead.

5. LANGUAGE MATCHING:
   - The user asked in: {lang_mode}.
   - ALWAYS reply in the EXACT SAME language ({lang_mode})!
   - If Hindi: Reply strictly in natural, polite Hindi using Devanagari script.
   - If Hinglish: Reply strictly in natural, conversational Hinglish using the Roman alphabet.
   - If English: Reply in clear, polished, professional English.

6. DATE & TIME (IST ONLY):
   - Check-in and check-out timestamps must ALWAYS be converted and displayed in India Standard Time (IST / Asia-Kolkata).
   - NEVER display raw UTC timestamps (such as '2026-07-28T04:18:39.778Z'). Always format cleanly in IST.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.45,
                max_tokens=800
            )

            text = self._response_text(response)
            if text:
                return text
        except Exception:
            pass

        from app.Services.structured_query import StructuredQueryRouter
        return StructuredQueryRouter.format_result(result, user_query)

    def generate_small_talk_response(
        self,
        user_query,
        employee_id,
        conversation_history=None,
        lang_mode=None,
    ):
        if not lang_mode:
            lang_mode = detect_language_mode(user_query)

        prompt = f"""
You are the conversational layer of an employee assistant.

Employee ID: {employee_id}
Recent conversation:
{json.dumps(conversation_history or [], ensure_ascii=False)}
Message: {user_query}

Rules:
- LANGUAGE MATCHING (CRITICAL):
  * Detected Language: {lang_mode}.
  * YOU MUST REPLY IN THE EXACT SAME LANGUAGE ({lang_mode})!
  * If Hindi: Reply in natural Hindi in Devanagari script (e.g. "नमस्ते! मैं आपकी किस प्रकार सहायता कर सकता हूँ?").
  * If Hinglish: Reply in natural, friendly Hinglish in Roman English alphabet (e.g. "Namaste! Main aapki kya madad kar sakta hoon?", "Theek hai, batayein main aapki kya madad karoon?").
  * If English: Reply in natural English (e.g. "Hello! How can I help you today?").
- LENGTH: Exactly 1 short, polite sentence (maximum 2).
- Distinguish greetings, acknowledgements, agreement, and refusal naturally.
- Do not claim employee data was retrieved.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=300
        )

        text = self._response_text(response)

        if not text:
            # Fallback if reasoning model didn't emit text
            if lang_mode == "Hindi":
                return "नमस्ते! मैं आपकी किस प्रकार सहायता कर सकता हूँ?"
            elif lang_mode == "Hinglish":
                return "Namaste! Main aapki kya madad kar sakta hoon?"
            return "Hello! How can I help you today?"

        return text

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

        asks_absent = (
            "absent" in query_lower
            or "अबसेंट" in query_lower
        )

        asks_lifeline = (
            "lifeline" in query_lower
            or "early checkout" in query_lower
            or "late checkout" in query_lower
            or "late check-in" in query_lower
            or "late check in" in query_lower
        )

        asks_worked_total = (
            (
                ("hour" in query_lower or "hours" in query_lower)
                and ("total" in query_lower or "worked" in query_lower)
            )
            or "working hours" in query_lower
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

        lines = []

        if summary:
            month = summary.get("month", "")
            try:
                month = datetime.strptime(
                    f"{month}-01",
                    "%Y-%m-%d"
                ).strftime("%B %Y")
            except (TypeError, ValueError):
                pass

            period_text = f" ({month})" if month else ""
            lines.append(f"### Attendance Summary{period_text}\n")
            lines.append(f"- **Present:** {summary.get('present', 0)} day(s)")
            lines.append(f"- **Half-day:** {summary.get('half_day', 0)} day(s)")
            lines.append(f"- **Absent:** {summary.get('absent', 0)} day(s)")
            lines.append(f"- **Total Records:** {summary.get('total_records', len(records))} day(s)")
            if summary.get("total_worked_hours") is not None:
                lines.append(
                    f"- **Total Working Time:** {summary.get('total_worked_hours', 0)} hour(s) and "
                    f"{summary.get('remaining_worked_minutes', 0)} minute(s)"
                )
            lines.append("")

        lines.append("### Recent Attendance Records\n")

        for record in records:

            date = record.get("date", "Unknown date")

            try:
                parsed_date = datetime.strptime(
                    date,
                    "%Y-%m-%d"
                )

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

            lines.append(
                f"{details[0]} " + ", ".join(details[1:]) + "."
            )

        lines.append(
            "\nThese records are shown using your attendance data. "
            "Let me know if you would like to see a specific date or month."
        )

        return "\n".join(lines)

    @staticmethod
    def _attendance_time(value):
        if not value:
            return ""

        try:
            return datetime.strptime(
                str(value),
                "%Y-%m-%d %I:%M %p IST"
            ).strftime("%I:%M %p IST")
        except (TypeError, ValueError):
            pass

        formatted = format_india_datetime(value)
        if formatted:
            try:
                return datetime.strptime(
                    formatted,
                    "%Y-%m-%d %I:%M %p IST"
                ).strftime("%I:%M %p IST")
            except Exception:
                return formatted
        return str(value)

    @staticmethod
    def _format_summary_date(value):

        try:
            parsed_date = datetime.strptime(
                value,
                "%Y-%m-%d"
            )

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
                "date": (
                    today - timedelta(days=1)
                ).isoformat()
            }

        if "today" in query_lower or "आज" in query_lower:
            return {
                "date": today.isoformat()
            }

        iso_date = re.search(
            r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b",
            query_lower
        )

        if iso_date:

            year, month, day = iso_date.groups()

            return {
                "date": (
                    f"{int(year):04d}-"
                    f"{int(month):02d}-"
                    f"{int(day):02d}"
                )
            }

        month_names = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12
        }

        for month_name, month_number in month_names.items():

            if month_name in query_lower:

                year_match = re.search(
                    r"\b(20\d{2})\b",
                    query_lower
                )

                return {
                    "month": month_number,
                    "year": (
                        int(year_match.group(1))
                        if year_match
                        else today.year
                    )
                }

        return {}

    def genreate_response(
        self,
        query,
        context=None,
        employee_id=None,
        user_query=None,
        conversation_history=None,
        lang_mode=None,
    ):
        if not lang_mode:
            lang_mode = detect_language_mode(query)

        current_india_time = datetime.now(
            self.INDIA_TIMEZONE
        ).strftime("%Y-%m-%d %I:%M %p IST")
        prompt = f"""
You are an AI Employee Assistant.

Help employees with employee data, company information and general questions.

DETECTED USER LANGUAGE: {lang_mode}
YOU MUST REPLY IN: {lang_mode}

LANGUAGE MATCHING (CRITICAL):
- ALWAYS reply in the EXACT SAME language the employee used ({lang_mode}):
  * If Hindi: reply strictly in natural Hindi (Devanagari script only).
  * If Hinglish: reply strictly in natural conversational Hinglish (Roman English alphabet only, e.g. "Aap portal par jakar apply kar sakte hain.").
  * If English: reply in clear English.
- Never translate Hindi or Hinglish questions into English responses.

RESPONSE STYLE & FORMAT (CRITICAL):
- Speak like a friendly, intelligent, articulate HR AI assistant (like ChatGPT).
- Answer single-fact questions (designation, shift, branch, check-in time) in complete, natural, polite conversational sentences, NOT raw key-value headers.
- For attendance queries: provide a conversational summary (Present, Half-day, Absent, total records, worked hours) followed by recent records with check-in and check-out times in IST.
- For leave balance queries: state the total remaining leaves and show each leave type separately with allocated, used, and remaining days.
- For timestamps: ALWAYS display check-in and check-out times in India Standard Time (IST / Asia-Kolkata). Never display raw UTC timestamps.
- Use clean bullet points (- ) with bold highlights instead of markdown tables with pipe (|) characters.
- Do not unnecessarily compress multiple records into a single confusing sentence.
- Do not generate long articles, introductions, tips, conclusions, or essays. Answer what was asked in a helpful, conversational manner.
- For leave process (e.g. "leaves kaise apply karte hain?"): give only the actual, concise steps from Company Context.

EMPLOYEE AND COMPANY QUESTIONS:
- Use the appropriate employee tool when personal employee data is required.
- Use Company Context for company-specific information.
- Never invent employee data or company policies.
- Always use the employee_id provided by the application ({employee_id}). Never ask the user for their employee ID.
- For attendance use get_attendance.
- For leave balance / remaining leaves use get_leave_balance.
- For leave requests use get_leave_requests.
- For leave policy use get_leave_types.
- For holidays use get_holidays.
- For employee profile use get_employee.
- For shift use get_employee_shift.
- For branch use get_employee_branch.
- For designation use get_employee_designation.

GENERAL QUESTIONS:
- If the question is not related to employee or company data, answer it directly using your general knowledge in the same language.
- Do not call employee tools for general questions.
- Do not force general questions into employee or company context.
- Do not say information is unavailable just because it is not present in Company Context.
- Do not invent facts.

RESPONSE RULES:
- Answer clearly, naturally and directly.
- Do not mention tools, prompts, JSON, routing or internal implementation.
- Do not expose MongoDB IDs or internal database fields.
- Use the employee_id provided by the application for personal employee information.
- Use the current India date and time when interpreting today, yesterday, now or current.

Company Context:
{context}

Recent conversation:
{json.dumps(conversation_history or [], ensure_ascii=False)}

User Question:
{query}

Current date and time in India:
{current_india_time}
"""

        tool_used = None
        tool_result = None

        messages = [
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": query
            }
        ]

        for _ in range(3):

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                temperature=0.45,
                max_tokens=800
            )

            message = response.choices[0].message
            function_calls = message.tool_calls

            if not function_calls:

                text = self._response_text(response)

                if text:
                    return {
                        "type": "message",
                        "response": text,
                        "tool_used": tool_used,
                        "tool_result": tool_result
                    }

                break

            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                    for tool_call in function_calls
                ]
            })

            for tool_call in function_calls:

                function_name = tool_call.function.name

                try:
                    arguments = json.loads(
                        tool_call.function.arguments
                    )
                except json.JSONDecodeError:
                    arguments = {}

                result = self._run_tool(
                    function_name,
                    arguments,
                    employee_id=employee_id
                )

                if result is None:
                    continue

                tool_used = function_name
                tool_result = result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str
                    )
                })

        if lang_mode == "Hindi":
            fallback = (
                "मुझे इस बारे में पूरी जानकारी नहीं मिल पाई। "
                "कृपया अपने एम्प्लॉई डेटा या कंपनी पॉलिसी के बारे में पूछें।"
            )
        elif lang_mode == "Hinglish":
            fallback = (
                "Mujhe is baare mein sahi jaankari nahi mil paayi. "
                "Kripya apne employee data ya company policy ke baare mein poochein."
            )
        else:
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