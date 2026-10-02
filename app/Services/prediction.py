from app.Services.entity_extractor import EntityExtractor
from app.Services.context import ConversationContext
import joblib


class IntentPredictionService:

    def __init__(self):
        self.model = joblib.load("Model/intent_model.pkl")
        self.vectorizer = joblib.load("Model/tfidf_vectorizer.pkl")
        self.entity_extractor = EntityExtractor()
        self.context = ConversationContext()

    def predict(self, query):
        query_vector = self.vectorizer.transform([query])
        intent = self.model.predict(query_vector)[0]
        probabilities = self.model.predict_proba(query_vector)[0]
        confidence = max(probabilities)
        entities = self.entity_extractor.extract(query)

        previous_context = self.context.get()
        is_follow_up = self.context.is_follow_up(query)

        q_lower = query.casefold()
        domain_keywords = {
            "leave": ["leave", "leaves", "chutti", "chhutti", "छुट्टी"],
            "attendance": ["attendance", "check in", "check out", "उपस्थिति", "हाजिरी"],
            "salary": ["salary", "pay", "payslip", "वेतन"],
            "holiday": ["holiday", "holidays", "त्योहार", "छुट्टियां"],
            "profile": ["profile", "designation", "shift", "branch"],
        }

        has_explicit_domain = any(
            any(w in q_lower for w in words)
            for words in domain_keywords.values()
        )
        is_qualifier = any(
            w in q_lower for w in ("wali", "wala", "us din", "that day", "ki?", "ka?")
        )

        if (is_follow_up or is_qualifier) and previous_context and not has_explicit_domain:
            intent = previous_context["intent"]
            entities = {**previous_context.get("entities", {}), **entities}

        self.context.update(intent, entities)

        return {
            "query": query,
            "intent": intent,
            "confidence": round(float(confidence), 2),
            "entities": entities,
        }