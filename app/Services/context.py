class ConversationContext:
    FOLLOW_UP_WORDS = ["aur", "also", "then", "what about", "how about"]

    def __init__(self):
        self.context = {}

    def is_follow_up(self, query):
        query = query.lower().strip()
        return any(query.startswith(word) for word in self.FOLLOW_UP_WORDS)

    def update(self, intent, entities):
        self.context["intent"] = intent
        self.context["entities"] = entities

    def get(self):
        return self.context

    def clear(self):
        self.context = {}