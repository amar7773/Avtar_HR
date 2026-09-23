import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
from app.Tools.employee_tools import get_salary,get_attendance,get_experience,get_projects,SALARY_TOOL,ATTENDANCE_TOOL,EXPERIENCE_TOOL,PROJECT_TOOL

load_dotenv()
class LLMServices:
    def __init__(self):
        self.client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-3.6-flash"
        self.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="get_salary",
                        description=(
                            "Get salary information for an employee "
                            "for a specific month or available salary records."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="INTEGER",
                                    description="The employee ID."
                                ),
                                "month": types.Schema(
                                    type="STRING",
                                    description="Salary month."
                                )
                            },
                            required=["employee_id"]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_attendance",
                        description=(
                            "Get attendance records for an employee."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="INTEGER",
                                    description="The employee ID."
                                )
                            },
                            required=["employee_id"]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_experience",
                        description=(
                            "Get work experience information for an employee."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="INTEGER",
                                    description="The employee ID."
                                )
                            },
                            required=["employee_id"]
                        )
                    ),

                    types.FunctionDeclaration(
                        name="get_projects",
                        description=(
                            "Get project information for an employee."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "employee_id": types.Schema(
                                    type="INTEGER",
                                    description="The employee ID."
                                )
                            },
                            required=["employee_id"]
                        )
                    )
                ]
            )
        ]
    def genreate_response(self,query,context=None):
        prompt = f"""
You are an AI Employee Assistant.

Your job is to help employees with:

- Salary
- Attendance
- Work experience
- Projects
- Company policies
- Company-related information
- General questions about the employee assistant

IMPORTANT RULES:

1. If the user asks for personal employee information such as
   salary, attendance, experience, or projects, use the appropriate
   employee tool.

2. Use the provided company context when answering questions about
   company policies or company-specific information.

3. Do not invent company policies, rules, benefits, or employee data.

4. If a company-specific answer is not available in the provided
   context or employee tools, clearly say that the information
   is not available.

5. For general questions about the employee assistant, answer
   naturally without requiring company context.

6. Give clear, concise, and natural answers.

7. Use the employee_id provided by the tool arguments when calling
   employee data tools.

Company Context:
{context}

User Question:
{query}
"""

        response = self.client.models.generate_content(model=self.model,contents=prompt,config=types.GenerateContentConfig(tools=self.tools))
        for part in response.candidates[0].content.parts:
            if part.function_call:
                function_call = part.function_call
                function_name = function_call.name
                arguments = dict(function_call.args)
                if function_name == "get_salary":
                    result = get_salary(
                        employee_id=arguments["employee_id"],
                        month=arguments.get("month")
                    )
                elif function_name == "get_attendance":
                    result = get_attendance(
                        employee_id=arguments["employee_id"]
                    )
                elif function_name == "get_experience":

                    result = get_experience(
                        employee_id=arguments["employee_id"]
                    )
                elif function_name == "get_projects":
                    result = get_projects(employee_id=arguments["employee_id"])
                else:
                    continue
                second_response = self.client.models.generate_content(
                    model=self.model,
                    contents=[
                        prompt,
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
                    ],
                    config=types.GenerateContentConfig(
                        tools=self.tools
                    )
                )

                return {
                    "type": "message",
                    "response": second_response.text,
                    "tool_used": function_name,
                    "tool_result": result
                }
        return {
            "type": "message",
            "response": response.text
        }