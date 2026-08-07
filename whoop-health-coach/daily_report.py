from app import get_whoop_data
from app import generate_health_report


print("DAILY REPORT START")


data = get_whoop_data()


report = generate_health_report(data)


print(report)


print("DAILY REPORT END")
