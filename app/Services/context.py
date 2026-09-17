class ConverSationContext:
    FOLLOW_UP_WORDS = [
        "aur",
        "also",
        "then",
        "what about",
        "how about"
    ]
    def __init__(self):
        self.context={}
    def is_follow_up(self,query):
        query=query.lower().strip()
        for word in self.FOLLOW_UP_WORDS:
            if query.startswith(word):
                return True
        return False
    def update(self,intent,entities):
        self.context["intent"]=intent
        self.context["entities"]=entities
    def get(self):
        return self.context
    def clear(self):
        self.context={}