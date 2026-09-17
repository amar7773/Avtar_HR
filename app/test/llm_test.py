from app.Services.Assistant import AssistantService


assistant = AssistantService()


queries = [
    "How can I apply for leave?",
    "What should I do for an expense claim?",
    "August ki meri salary batao"
]


for query in queries:

    print("\n==============================")
    print("QUERY:", query)

    result = assistant.process(
        user_query=query,
        employee_id=101
    )

    print("\nIntent:", result["intent"])
    print("Confidence:", result["confidence"])
    print("Tool:", result["tool_used"])
    print("Response:", result["response"])