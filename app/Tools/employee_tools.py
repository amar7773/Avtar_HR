from app.Services.Data_services import DataService


data_service = DataService()


def get_salary(employee_id, month=None):

    data = data_service.get_salary(employee_id)

    if month:
        data = data[
            data["month"].str.lower() == month.lower()
        ]

    if data.empty:
        return {
            "success": False,
            "message": "Salary information not found."
        }

    return {
        "success": True,
        "data": data.to_dict(
            orient="records"
        )
    }
def get_attendance(employee_id):

    data = data_service.get_attendance(employee_id)

    if data.empty:
        return {
            "success": False,
            "message": "Attendance information not found."
        }

    return {
        "success": True,
        "data": data.to_dict(
            orient="records"
        )
    }


def get_experience(employee_id):

    data = data_service.get_experience(employee_id)

    if data.empty:
        return {
            "success": False,
            "message": "Experience information not found."
        }

    return {
        "success": True,
        "data": data.to_dict(
            orient="records"
        )
    }


def get_projects():

    data = data_service.get_projects()

    if data.empty:
        return {
            "success": False,
            "message": "Project information not found."
        }

    return {
        "success": True,
        "data": data.to_dict(
            orient="records"
        )
    }

SALARY_TOOL = {
    "type": "function",
    "name": "get_salary",
    "description": (
        "Get salary information for an employee "
        "for a specific month or available salary records."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "integer",
                "description": "The employee ID."
            },
            "month": {
                "type": "string",
                "description": "Salary month."
            }
        },
        "required": ["employee_id"],
        "additionalProperties": False
    }
}


ATTENDANCE_TOOL = {
    "type": "function",
    "name": "get_attendance",
    "description": (
        "Get attendance records for an employee."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "integer",
                "description": "The employee ID."
            }
        },
        "required": ["employee_id"],
        "additionalProperties": False
    }
}


EXPERIENCE_TOOL = {
    "type": "function",
    "name": "get_experience",
    "description": (
        "Get work experience information for an employee."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "integer",
                "description": "The employee ID."
            }
        },
        "required": ["employee_id"],
        "additionalProperties": False
    }
}


PROJECT_TOOL = {
    "type": "function",
    "name": "get_projects",
    "description": (
        "Get available project information."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False
    }
}