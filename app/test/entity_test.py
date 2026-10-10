import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.Services.entity_extractor import EntityExtractor


def test_entity_extraction():
    extractor = EntityExtractor()
    queries = [
        "August mein meri salary batao",
        "July 2026 ki attendance batao",
        "tell me my salary",
        "when did I join the company"
    ]
    for query in queries:
        entities = extractor.extract(query)
        assert isinstance(entities, dict)


if __name__ == "__main__":
    test_entity_extraction()