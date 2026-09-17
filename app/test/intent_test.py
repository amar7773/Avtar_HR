from app.Services.prediction import IntentPredictionService


predictor = IntentPredictionService()


queries = [
    "August ki attendance batao",
    "Aur July ki?",
    "Aur June ki?",
    "Python projects batao"
]


for query in queries:

    result = predictor.predict(query)

    print("\nQuery:", query)
    print("Intent:", result["intent"])
    print("Entities:", result["entities"])