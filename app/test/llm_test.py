from app.Services.Assistant import AssistantService


assistant = AssistantService()


result = assistant.process(
    user_query="August ki meri salary batao",
    employee_id=101
)


print("\n========== ASSISTANT ==========")

print("\nUser Query:")
print(result["user_query"])

print("\nIntent:")
print(result["intent"])

print("\nConfidence:")
print(result["confidence"])

print("\nEntities:")
print(result["entities"])

print("\nTool Used:")
print(result["tool_used"])

print("\nTool Result:")
print(result["tool_result"])

print("\nFinal Response:")
print(result["response"])