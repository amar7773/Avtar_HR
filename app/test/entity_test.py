from app.Services.entity_extractor import EntityExtractor


extractor = EntityExtractor()


queries = [
    "August mein meri salary batao",
    "July 2026 ki attendance batao",
    "mere Python projects batao",
    "tell me my salary",
    "when did I join the company"
]


for query in queries:

    entities = extractor.extract(query)

    print("\nQuery:", query)
    print("Entities:", entities)