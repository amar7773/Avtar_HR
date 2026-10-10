import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.Services.prediction import IntentPredictionService


def test_intent_prediction():
    predictor = IntentPredictionService()
    queries = [
        "August ki attendance batao",
        "Aur July ki?",
        "Python projects batao"
    ]
    for query in queries:
        result = predictor.predict(query)
        assert result is not None
        assert "intent" in result


if __name__ == "__main__":
    test_intent_prediction()