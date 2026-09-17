from app.Data_Source.csv_source import CSVDataSource

class DataService:
    def __init__(self):
        self.source=CSVDataSource("data")
    def get_attendance(self,employee_id):
        data=self.source.get_data("attendance")
        result = data[data["employee_id"] == employee_id]
        return result
    def get_experience(self,employee_id):
        data=self.source.get_data("employees")
        result = data[data["employee_id"] == employee_id]
        return result
    def get_projects(self,employee_id):
        data=self.source.get_data("projects")
        result = data[data["employee_id"] == employee_id]
        return result
    def get_salary(self,employee_id):
        data=self.source.get_data("salary")
        result = data[data["employee_id"] == employee_id]
        return result