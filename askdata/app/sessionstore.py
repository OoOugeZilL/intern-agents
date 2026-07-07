"""Stores lightweight in-memory session context for follow-up questions."""


class SessionStore:
    """Stores session context in memory for V1 follow-up questions."""

    def __init__(self):
        self.sessions = {}

    def Get(self, sessionId):
        """Returns the saved session context or an empty context."""
        return self.sessions.get(sessionId, {})

    def Save(self, sessionId, context):
        """Saves the compact session context for a session id."""
        self.sessions[sessionId] = context

    def Reset(self, sessionId):
        """Clears one session context."""
        self.sessions.pop(sessionId, None)

