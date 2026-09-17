import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from app.Tools.employee_tools import get_salary,get_attendance,get_experience,get_projects,SALARY_TOOL,ATTENDANCE_TOOL,EXPERIENCE_TOOL,PROJECT_TOOL

load_dotenv()
class LLMServices:
    def __init__(self):
        self.client=OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-5.6-luna"
    def genreate_response(self,query,context=None):
        prompt = f"""
You are an employee assistant.

Answer the user's question using the provided
company context when the question is about
company policies or general company information.

Do not invent company policies.

If the answer is not available in the context,
say that the information is not available.

Company Context:
{context}

User Question:
{query}

Give a clear and natural answer.
"""
        response=self.client.responses.create(model=self.model,input=prompt,tools=[SALARY_TOOL,ATTENDANCE_TOOL,EXPERIENCE_TOOL,PROJECT_TOOL])
        for item in response.output:
            if item.type=="function_call":
                if item.name=="get_salary":
                    arguments = json.loads(item.arguments)
                    result=get_salary(employee_id=arguments["employee_id"],month=arguments.get("month"))
                elif item.name=="get_attendance":
                    arguments = json.loads(item.arguments)
                    result=get_attendance(employee_id=arguments["employee_id"])
                elif item.name=="get_experience":
                    arguments = json.loads(item.arguments)
                    result=get_experience(employee_id=arguments["employee_id"])
                elif item.name=="get_projects":
                    result=get_projects()
                else:
                    continue

                second_response=self.client.responses.create(model=self.model,
                input=[ *response.output,
                            {
                                "type": "function_call_output",
                                "call_id": item.call_id,
                                "output": json.dumps(result)
                            }], tools=[SALARY_TOOL,ATTENDANCE_TOOL,EXPERIENCE_TOOL,PROJECT_TOOL])
                return {
                        "type": "message",
                        "response": second_response.output_text,
                        "tool_used": item.name,
                        "tool_result": result
                    }

        return {
            "type":"message",
            "response":response.output_text
        } 