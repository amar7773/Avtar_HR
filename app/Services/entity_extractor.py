import re

MONTHS = {"january": "January","february": "February","march": "March",
    "april": "April","may": "May","june": "June","july": "July",
    "august": "August","september": "September","october": "October",
    "november": "November","december": "December","jan": "January",
    "feb": "February","mar": "March","apr": "April",
    "jun": "June","jul": "July","aug": "August","sep": "September",
    "oct": "October","nov": "November","dec": "December"
}
TECHNOLOGIES = ["python","java","react","javascript","node","fastapi",
        "tensorflow","pytorch","machine learning","deep learning"]

class EntityExtractor:
    def extract(self, query):
        query_lower = query.lower()
        entities = {}
        for month in MONTHS:
            if re.search(
                rf"\b{re.escape(month)}\b",query_lower):
                entities["month"] = MONTHS[month]
                break
        year = re.search(
            r"\b(20\d{2})\b",
            query
        )
        if year:
            entities["year"] = year.group(1)
        for technology in TECHNOLOGIES:
            if technology in query_lower:
                entities["technology"] = technology
                break
        return entities