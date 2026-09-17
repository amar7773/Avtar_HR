from app.Services.entity_extractor import EntityExtractor
from app.Services.context import ConverSationContext
import joblib

class IntentPredictionService:

    def __init__(self):

        self.model = joblib.load("Model/intent_model.pkl")
        self.vectorizer = joblib.load("Model/tfidf_vectorizer.pkl")
        self.entity_extractor=EntityExtractor()
        self.context=ConverSationContext()
    def predict(self, query):
        query_vector = self.vectorizer.transform([query])
        intent = self.model.predict(query_vector)[0]
        probabilities = self.model.predict_proba(query_vector)[0]
        confidence = max(probabilities)
        entities=self.entity_extractor.extract(query)
        previous_context = self.context.get()
        is_follow_up=self.context.is_follow_up(query)
        if is_follow_up and previous_context:
            intent=previous_context["intent"]
            entities = {**previous_context.get("entities", {}), **entities}
        self.context.update(
            intent,
            entities
        )
        return {
            "query": query,
            "intent": intent,
            "confidence": round(float(confidence), 2),
            "entities": entities
        }