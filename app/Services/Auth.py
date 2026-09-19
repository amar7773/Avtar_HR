from app.Services.Data_services import DataService


class AuthService:

    def __init__(self):
        self.data_service = DataService()

    def login(self, employee_id):

        experience = self.data_service.get_experience(employee_id)

        if experience.empty:
            return {
                "success": False,
                "message": "Employee ID not found."
            }

        employee = experience.iloc[0]

        return {
            "success": True,
            "employee": {
                "employee_id": int(employee["employee_id"]),
                "name": employee["name"],
                "department": employee["department"],
                "designation": employee["designation"]
            }
        }