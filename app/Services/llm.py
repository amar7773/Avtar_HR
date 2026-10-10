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
    format_india_datetime,
)
from app.Services.structured_query import StructuredQueryRouter

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
        "jyada", "zyada", "thoda", "thodi", "sunao", "kaunsa", "kaunsi", "kaunse",
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

        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        self.fallback_models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

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
                                "description": "Employee ID such as EMP-0013.",
                            }
                        },
                        "required": ["employee_id"],
                    },
                },
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
                                "description": "Employee ID such as EMP-0013.",
                            },
                            "date": {
                                "type": "string",
                                "description": "Specific date in YYYY-MM-DD format.",
                            },
                            "month": {
                                "type": "integer",
                                "description": "Month number from 1 to 12.",
                            },
                            "year": {
                                "type": "integer",
                                "description": "Year such as 2026.",
                            },
                        },
                        "required": ["employee_id"],
                    },
                },
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
                                "description": "Employee ID such as EMP-0013.",
                            },
                            "status": {
                                "type": "string",
                                "description": (
                                    "Leave status such as approved, "
                                    "rejected or pending."
                                ),
                            },
                        },
                        "required": ["employee_id"],
                    },
                },
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
                                "description": "Employee ID such as EMP-0013.",
                            }
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_leave_types",
                    "description": (
                        "Get active company leave types and their leave policies."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
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
                                "description": "Year such as 2026.",
                            },
                            "month": {
                                "type": "integer",
                                "description": "Month number from 1 to 12.",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_employee_shift",
                    "description": (
                        "Get the shift assigned to an employee "
                        "including start time, end time and working days."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "Employee ID such as EMP-0013.",
                            }
                        },
                        "required": ["employee_id"],
                    },
                },
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
                                "description": "Employee ID such as EMP-0013.",
                            }
                        },
                        "required": ["employee_id"],
                    },
                },
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
                                "description": "Employee ID such as EMP-0013.",
                            }
                        },
                        "required": ["employee_id"],
                    },
                },
            },
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

        # Inject the authenticated employee_id for personal data tools
        if employee_id and function_name in {
            "get_employee",
            "get_attendance",
            "get_leave_balance",
            "get_leave_requests",
            "get_employee_shift",
            "get_employee_branch",
            "get_employee_designation",
        }:
            arguments["employee_id"] = employee_id

        if function_name == "get_employee":
            return get_employee(employee_id=arguments["employee_id"])

        if function_name == "get_attendance":
            return get_attendance(
                employee_id=arguments["employee_id"],
                date=arguments.get("date"),
                month=arguments.get("month"),
                year=arguments.get("year"),
            )

        if function_name == "get_leave_balance":
            return get_leave_balance(employee_id=arguments["employee_id"])

        if function_name == "get_leave_requests":
            return get_leave_requests(
                employee_id=arguments["employee_id"],
                status=arguments.get("status"),
            )

        if function_name == "get_leave_types":
            return get_leave_types()

        if function_name == "get_holidays":
            return get_holidays(
                year=arguments.get("year"),
                month=arguments.get("month"),
            )

        if function_name == "get_employee_shift":
            return get_employee_shift(employee_id=arguments["employee_id"])

        if function_name == "get_employee_branch":
            return get_employee_branch(employee_id=arguments["employee_id"])

        if function_name == "get_employee_designation":
            return get_employee_designation(employee_id=arguments["employee_id"])

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

        payload = json.dumps(result, ensure_ascii=False, default=str)

        # Build conversation context summary for follow-up awareness
        context_note = ""
        if conversation_history:
            last_topics = [
                msg.get("content", "")[:80]
                for msg in conversation_history[-4:]
                if msg.get("role") == "user"
            ]
            if last_topics:
                context_note = f"\nRecent topics discussed: {' | '.join(last_topics)}"

        prompt = f"""You are an intelligent, friendly, and articulate AI Employee Assistant (like ChatGPT or Google Gemini) speaking directly with an employee.

Employee ID: {employee_id}
Detected User Language: {lang_mode}
Recent conversation history (for follow-up context):
{json.dumps(conversation_history or [], ensure_ascii=False)}{context_note}

User Question: {user_query}

Verified application data (ground truth — treat as the ONLY source of truth):
{payload}

RULES FOR EXACT, QUERY-SPECIFIC AND NATURAL RESPONSES:

1. CONVERSATION CONTEXT & FOLLOW-UPS (CRITICAL):
   - If this appears to be a follow-up question (e.g., "aur?", "what about last month?", "show more", "pichle mahine ka bhi batao"), use the conversation history to understand what was being discussed and provide a continuation.
   - If the question is ambiguous AND cannot be answered from the data (e.g., "mera kya hoga?", "what about that?"), politely ask ONE specific clarifying question.
   - Example clarification (Hinglish): "Aap attendance ke baare mein pooch rahe hain ya leave ke baare mein?"
   - Example clarification (Hindi): "क्या आप अटेंडेंस के बारे में जानना चाहते हैं या लीव के बारे में?"
   - Example clarification (English): "Are you asking about your attendance or your leave balance?"

2. EXACT QUERY INTENT (CRITICAL):
   - Answer the employee's EXACT question directly from the verified application data.
   - Do NOT return unrelated summaries, whole-month statistics, or dump raw data when a specific question is asked.
   - Specific intents:
     * Check-in Time: Answer ONLY the check-in time on that date in IST. If not recorded, state that no check-in record is available.
     * Check-out Time: Answer ONLY the check-out time on that date in IST. If not recorded, state that no check-out record is available.
     * Working Hours: Answer ONLY the hours and minutes worked on that date.
     * Presence / Status: Answer directly whether Present, Half Day, or Absent. Include check-in, check-out, and worked hours if available.
     * Total Attendance: Provide summary counts (Present, Half-day, Absent, Total records, Worked hours). Do NOT list individual dates unless explicitly asked.
     * Month Attendance: Provide a polite summary followed by recent records with Date, Status, Check-in (IST), Check-out (IST), and Worked hours.
     * Leave Balance: State total remaining leaves and break down each leave type (allocated, used, remaining).
     * Shift / Branch / Designation / Profile / Holidays: Answer conversationally with the exact assigned details.

3. STRICT MODULE SEPARATION:
   - Attendance queries must use attendance data only.
   - Leave queries must use leave data only.
   - Holiday queries must use holiday data only.
   - Never answer an attendance question using leave data or vice versa.

4. DATA INTEGRITY (CRITICAL — DO NOT INVENT DATA):
   - ONLY use the exact values from the "Verified application data" section above.
   - NEVER guess, estimate, or fabricate check-in times, check-out times, leave counts, salaries, or any other data.
   - If a field is null, missing, or not present in the verified data, clearly state: "This information is not recorded" or equivalent in the user's language.
   - NEVER say information exists when it does not appear in the verified data.
   - NEVER round up or approximate numbers. Always use the exact values given.

5. VOICE & DISPLAY FRIENDLY (NO RAW TABLES):
   - DO NOT use markdown tables with pipe (|) characters or ASCII grids.
   - Use clean bullet points (- ) with bold highlights for numbers and key terms instead.

6. LANGUAGE MATCHING (CRITICAL):
   - The user asked in: {lang_mode}.
   - ALWAYS reply in the EXACT SAME language ({lang_mode})!
   - If Hindi: Reply strictly in natural, polite Hindi using Devanagari script.
   - If Hinglish: Reply strictly in natural, conversational Hinglish using the Roman alphabet.
   - If English: Reply in clear, polished, professional English.
   - Never mix scripts (do not reply in English when user asked in Hindi).

7. DATE & TIME (IST ONLY):
   - Check-in and check-out timestamps must ALWAYS be converted and displayed in India Standard Time (IST / Asia-Kolkata).
   - NEVER display raw UTC timestamps. Always format cleanly in IST.

8. NATURAL HUMAN SPOKEN DELIVERY (CRITICAL FOR LIVE AVATAR):
   - You are speaking aloud through a live avatar. Speak naturally, warmly, and directly.
   - NEVER start with robotic template openings ("Certainly!", "Of course!", "Sure!", "Sure, I can help with that!", "Here is the information you requested:", or "As an AI..."). Jump directly into the natural answer.
   - Use natural contractions ("you're", "here's", "you were recorded as") so speech flows smoothly through speech synthesis.
   - For follow-up questions (e.g., "And what about yesterday?"), acknowledge the follow-up naturally: e.g. "Yesterday, on October 9th, your attendance was marked as Present..."
   - Do NOT add unnecessary disclaimers, repeated apologies, or repetitive closing summaries.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.45,
                max_tokens=800,
            )

            text = self._response_text(response)
            if text:
                return text
        except Exception:
            pass

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

        prompt = f"""You are the conversational speaking layer of an intelligent AI HR Employee Assistant talking with an employee through a live avatar.

Employee ID: {employee_id}
Detected User Language: {lang_mode}
Recent conversation history:
{json.dumps(conversation_history or [], ensure_ascii=False)}

User Message: "{user_query}"

RULES FOR NATURAL HUMAN-LIKE CONVERSATION:
1. Warm, authentic conversational presence:
   - Speak warmly and pleasantly, like a helpful HR colleague speaking face-to-face.
   - NEVER start with robotic template openings ("Certainly!", "Of course!", "Sure!", "Sure, I can help with that!", "As an AI language model...").
   - Keep answers concise (1 to 2 short, natural sentences). Never generate long paragraphs for small talk.
2. Match the specific conversational intent:
   - GREETING ("Hi", "Hello", "Good morning", "Hey"):
     * English: "Hello! Great to see you. How can I help you today?"
     * Hinglish: "Namaste! Kaise hain aap? Batayein aaj main aapki kya madad karoon?"
     * Hindi: "नमस्ते! आप कैसे हैं? बताइए आज मैं आपकी क्या सहायता कर सकता हूँ?"
   - WELL-BEING / SOCIAL ("How are you?", "How are you doing?", "Kaise ho?", "Kya haal hai?"):
     * English: "I'm doing great, thank you for asking! How are things with you?"
     * Hinglish: "Main bilkul badhiya hoon, poochhne ke liye shukriya! Aap bataiye, sab kaisa chal raha hai?"
     * Hindi: "मैं बिल्कुल ठीक हूँ, पूछने के लिए धन्यवाद! आप कैसे हैं?"
   - GRATITUDE ("Thank you", "Thanks", "Shukriya", "Dhanyawad"):
     * English: "You're very welcome! Let me know if you need anything else."
     * Hinglish: "Aapka swagat hai! Agar aur koi sawaal ho toh zaroor bataiye."
     * Hindi: "आपका बहुत-बहुत स्वागत है! अगर कोई और जानकारी चाहिए तो ज़रूर बताएं।"
   - ACKNOWLEDGEMENT / OKAY ("Okay", "Alright", "Theek hai", "Sure"):
     * English: "Sounds good! I'm right here whenever you need anything."
     * Hinglish: "Theek hai! Jab bhi zaroorat ho, bas bata dijiyega."
     * Hindi: "ठीक है! जब भी आवश्यकता हो, अवश्य बताएं।"
   - PARTING ("Bye", "Goodbye", "Alvida", "See you"):
     * English: "Goodbye! Have a productive and wonderful day ahead."
     * Hinglish: "Alvida! Aapka din shubh aur productive rahe."
     * Hindi: "अलविदा! आपका दिन शुभ रहे।"
   - IDENTITY / CAPABILITY ("Who are you?", "What can you do?", "Aap kaun ho?"):
     * English: "I'm your AI HR assistant. I can help you check your attendance, leave balances, company holidays, shift details, and more."
     * Hinglish: "Main aapka AI HR assistant hoon. Main aapki attendance, leave balance, company holidays, shift timings aur policies check karne mein madad karta hoon."
     * Hindi: "मैं आपका एआई एचआर सहायक हूँ। मैं आपकी अटेंडेंस, लीव बैलेंस, छुट्टियाँ और शिफ्ट डिटेल्स देखने में मदद कर सकता हूँ।"
3. STRICT LANGUAGE MATCHING:
   - You MUST reply strictly in {lang_mode}!
   - Never answer in English when asked in Hindi or Hinglish.
"""

        models_to_try = [self.model]
        for fb in getattr(self, "fallback_models", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]):
            if fb not in models_to_try:
                models_to_try.append(fb)

        text = None
        for m in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.65,
                    max_tokens=250,
                )
                text = self._response_text(response)
                if text:
                    break
            except Exception as e:
                print(f"[LLM WARNING] Small talk error with model {m}: {e}")
                continue

        if not text:
            q = user_query.casefold().strip()
            if any(w in q for w in ("how are you", "how are you doing", "kaise ho", "kya haal")):
                if lang_mode == "Hindi":
                    return "मैं बिल्कुल ठीक हूँ, पूछने के लिए धन्यवाद! आप कैसे हैं?"
                if lang_mode == "Hinglish":
                    return "Main bilkul badhiya hoon, poochhne ke liye shukriya! Aap bataiye, sab kaisa chal raha hai?"
                return "I'm doing great, thank you for asking! How are things with you?"
            if any(w in q for w in ("thank", "thanks", "shukriya", "dhanyawad")):
                if lang_mode == "Hindi":
                    return "आपका बहुत-बहुत स्वागत है! अगर कोई और जानकारी चाहिए तो ज़रूर बताएं।"
                if lang_mode == "Hinglish":
                    return "Aapka swagat hai! Agar aur koi sawaal ho toh zaroor bataiye."
                return "You're very welcome! Let me know if you need anything else."
            if any(w in q for w in ("ok", "okay", "theek", "thik", "theek hai")):
                if lang_mode == "Hindi":
                    return "ठीक है! जब भी आवश्यकता हो, अवश्य बताएं।"
                if lang_mode == "Hinglish":
                    return "Theek hai! Jab bhi zaroorat ho, bas bata dijiyega."
                return "Sounds good! I'm right here whenever you need anything."
            if any(w in q for w in ("bye", "goodbye", "alvida", "see you")):
                if lang_mode == "Hindi":
                    return "अलविदा! आपका दिन शुभ रहे।"
                if lang_mode == "Hinglish":
                    return "Alvida! Aapka din shubh aur productive rahe."
                return "Goodbye! Have a productive and wonderful day ahead."
            if any(w in q for w in ("who are you", "what can you do", "aap kaun")):
                if lang_mode == "Hindi":
                    return "मैं आपका एआई एचआर सहायक हूँ। मैं आपकी अटेंडेंस, लीव बैलेंस और कंपनी नीतियों की जानकारी दे सकता हूँ।"
                if lang_mode == "Hinglish":
                    return "Main aapka AI HR assistant hoon. Main aapki attendance, leave balance aur policies check karne mein madad karta hoon."
                return "I'm your AI HR assistant. I can help you check your attendance, leave balances, shift details, and company policies."
            if lang_mode == "Hindi":
                return "नमस्ते! मैं आपकी किस प्रकार सहायता कर सकता हूँ?"
            if lang_mode == "Hinglish":
                return "Namaste! Batayein aaj main aapki kya madad karoon?"
            return "Hello! How can I help you today?"

        return text

    def generate_response(
        self,
        query,
        context=None,
        employee_id=None,
        conversation_history=None,
        lang_mode=None,
    ):
        if not lang_mode:
            lang_mode = detect_language_mode(query)

        current_india_time = datetime.now(self.INDIA_TIMEZONE).strftime("%Y-%m-%d %I:%M %p IST")

        # Build conversation context summary for follow-up awareness
        context_note = ""
        if conversation_history:
            last_user_messages = [
                msg.get("content", "")[:100]
                for msg in conversation_history[-6:]
                if msg.get("role") == "user"
            ]
            if last_user_messages:
                context_note = (
                    f"\n\nRecent topics from conversation (for follow-up context): "
                    f"{' | '.join(last_user_messages[-3:])}"
                )

        prompt = f"""You are an AI Employee Assistant — intelligent, friendly, and articulate (like ChatGPT or Google Gemini).

Help employees with their personal employee data, company information and general questions.

DETECTED USER LANGUAGE: {lang_mode}
YOU MUST REPLY IN: {lang_mode}

CONVERSATION CONTEXT & FOLLOW-UPS (CRITICAL):
- This assistant maintains conversation memory. The recent conversation history is provided below.
- If the current user question appears to be a follow-up (e.g., "aur batao", "what about last month?", "phir?", "and?"), use the conversation history to understand the topic and provide a natural continuation.
- If the question is ambiguous (e.g., "mera kya haal hai?", "show me more", "details batao") and CANNOT be answered from context alone, ask ONE short, specific clarifying question in the SAME language ({lang_mode}).
  * Hinglish example: "Aap attendance ke baare mein pooch rahe hain ya leave balance ke baare mein?"
  * Hindi example: "क्या आप अटेंडेंस जानना चाहते हैं या छुट्टी की जानकारी?"
  * English example: "Could you clarify — are you asking about your attendance or your leave balance?"
- Never ask for the employee ID. It is already known: {employee_id}.

DATA INTEGRITY (CRITICAL — DO NOT INVENT):
- ONLY report data that comes from the employee tools (get_employee, get_attendance, get_leave_balance, etc.).
- NEVER guess, estimate, or fabricate check-in/check-out times, leave counts, salary, or any other personal data.
- If the tool returns no data or a field is null, state clearly that the information is not available.
- NEVER invent employee-specific data even if you think it "should" be there.
- For company policies, use Company Context only. Do not invent policies.

LANGUAGE MATCHING (CRITICAL):
- ALWAYS reply in the EXACT SAME language the employee used ({lang_mode}):
  * If Hindi: reply strictly in natural Hindi (Devanagari script only).
  * If Hinglish: reply strictly in natural conversational Hinglish (Roman English alphabet, e.g. "Aap portal par jakar apply kar sakte hain.").
  * If English: reply in clear, professional English.
- Never translate Hindi or Hinglish questions into English responses.
- Never mix scripts in the same response.

RESPONSE STYLE & FORMAT:
- Speak like a friendly, intelligent HR AI assistant speaking through a live avatar.
- NEVER use robotic template openings ("Certainly!", "Of course!", "Sure!", "Sure, I can help with that!", "As an AI language model..."). Answer directly, warmly, and clearly.
- Use natural contractions and conversational phrasing so spoken delivery sounds fluent.
- Answer single-fact questions (designation, shift, branch, check-in time) in complete, natural, polite conversational sentences.
- For attendance: provide a conversational summary then recent records with check-in/check-out times in IST.
- For leave balance: state total remaining leaves, then break down each leave type (allocated, used, remaining).
- ALWAYS display timestamps in India Standard Time (IST / Asia-Kolkata). NEVER display raw UTC timestamps.
- Use clean bullet points (- ) with bold highlights. DO NOT use markdown tables with pipe (|) characters.
- Do not generate long essays, introductions, or conclusions. Answer what was asked concisely.
- For leave process questions (e.g. "leaves kaise apply karte hain?"): give only the concise steps from Company Context.

EMPLOYEE TOOL USAGE:
- Use the appropriate employee tool when personal employee data is required.
- Always use employee_id: {employee_id} (never ask the user for it).
- For attendance: get_attendance
- For leave balance: get_leave_balance
- For leave requests: get_leave_requests
- For leave policy: get_leave_types
- For holidays: get_holidays
- For profile: get_employee
- For shift: get_employee_shift
- For branch: get_employee_branch
- For designation: get_employee_designation

GENERAL QUESTIONS:
- If not related to employee or company data, answer directly using general knowledge in the same language.
- Do not call employee tools for general questions.
- Do not say information is unavailable just because it is not in Company Context.
- Do not invent facts.

RESPONSE RULES:
- Answer clearly, naturally and directly.
- Do NOT mention tools, prompts, JSON, routing or internal implementation details.
- Do NOT expose MongoDB IDs or internal database fields.
- Use the current India date and time for interpreting "today", "yesterday", "now", "current".

Company Context:
{context}{context_note}

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
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ]

        models_to_try = [self.model]
        for fb in getattr(self, "fallback_models", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]):
            if fb not in models_to_try:
                models_to_try.append(fb)

        for current_model in models_to_try:
            try:
                current_messages = list(messages)
                tool_used = None
                tool_result = None

                for _ in range(3):
                    response = self.client.chat.completions.create(
                        model=current_model,
                        messages=current_messages,
                        tools=self.tools,
                        temperature=0.45,
                        max_tokens=800,
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
                                "tool_result": tool_result,
                            }
                        break

                    current_messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in function_calls
                        ],
                    })

                    for tool_call in function_calls:
                        function_name = tool_call.function.name
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                        result = self._run_tool(function_name, arguments, employee_id=employee_id)
                        if result is None:
                            continue

                        tool_used = function_name
                        tool_result = result

                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })
            except Exception as e:
                print(f"[LLM WARNING] Chat completion error with {current_model}: {e}")
                continue

        # Human-friendly fallback error messages in all 3 languages
        if lang_mode == "Hindi":
            fallback = (
                "मुझे इस बारे में पूरी जानकारी नहीं मिल पाई। "
                "क्या आप अपने अटेंडेंस, छुट्टी, प्रोफ़ाइल, शिफ्ट या कंपनी पॉलिसी के बारे में पूछना चाहते हैं?"
            )
        elif lang_mode == "Hinglish":
            fallback = (
                "Mujhe is sawaal ka sahi jawab nahi mil paya. "
                "Kya aap attendance, leave, profile, shift ya company policy ke baare mein poochna chahte hain?"
            )
        else:
            fallback = (
                "I wasn't able to find a reliable answer to that question. "
                "You can ask me about your attendance, leave balance, profile, shift schedule, holidays, or company policies."
            )

        return {
            "type": "message",
            "response": fallback,
            "tool_used": tool_used,
            "tool_result": tool_result,
        }