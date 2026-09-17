from app.Services.Data_services import DataService


data_service = DataService()

employee_id = 101


print("===== ATTENDANCE =====")

attendance = data_service.get_attendance(employee_id)

print(attendance)


print("\n===== EXPERIENCE =====")

experience = data_service.get_experience(employee_id)

print(experience)


print("\n===== SALARY =====")

salary = data_service.get_salary(employee_id)

print(salary)