import json
import queue
import time
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class SSEManager:
    """
    Thread-safe Server-Sent Events (SSE) Pub/Sub Manager.
    Manages client connections via per-user Queues and broadcasts events.
    """
    def __init__(self):
        # Map user_id -> List[queue.Queue]
        self._user_subscribers: Dict[int, List[queue.Queue]] = {}
        # Global subscribers (optional, e.g. for broadcast/admins)
        self._global_subscribers: List[queue.Queue] = []

    def subscribe(self, user_id: int) -> queue.Queue:
        """Register a subscriber queue for a specific user."""
        q = queue.Queue(maxsize=100)
        if user_id not in self._user_subscribers:
            self._user_subscribers[user_id] = []
        self._user_subscribers[user_id].append(q)
        logger.debug(f"[SSE] User {user_id} connected. Total active sessions: {len(self._user_subscribers[user_id])}")
        return q

    def unsubscribe(self, user_id: int, q: queue.Queue):
        """Remove a subscriber queue when the SSE connection is closed."""
        if user_id in self._user_subscribers:
            try:
                self._user_subscribers[user_id].remove(q)
                if not self._user_subscribers[user_id]:
                    del self._user_subscribers[user_id]
            except ValueError:
                pass
        logger.debug(f"[SSE] User {user_id} disconnected.")

    def publish_to_user(self, user_id: int, event_type: str, data: Any):
        """Send an SSE event payload to all open sessions of a specific user."""
        if user_id not in self._user_subscribers:
            logger.debug(f"[SSE] User {user_id} is not currently connected to SSE. Skipping live push.")
            return

        formatted_msg = self.format_sse(event_type=event_type, data=data)
        queues = self._user_subscribers.get(user_id, [])
        for q in list(queues):
            try:
                q.put_nowait(formatted_msg)
            except queue.Full:
                logger.warning(f"[SSE] Queue full for user {user_id}, dropping message.")

    def publish_broadcast(self, event_type: str, data: Any):
        """Broadcast an event to all connected users."""
        formatted_msg = self.format_sse(event_type=event_type, data=data)
        for user_id, queues in list(self._user_subscribers.items()):
            for q in list(queues):
                try:
                    q.put_nowait(formatted_msg)
                except queue.Full:
                    pass

    @staticmethod
    def format_sse(event_type: str, data: Any, event_id: str = None) -> str:
        """
        Format a message according to the SSE standard:
        event: <event_type>
        data: <json_string>
        id: <event_id> (optional)
        \n\n
        """
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        if event_type:
            lines.append(f"event: {event_type}")
        
        json_data = json.dumps(data) if not isinstance(data, str) else data
        lines.append(f"data: {json_data}")
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def format_ping() -> str:
        """Return a comment/ping to keep SSE connection alive."""
        return ": ping\n\n"


# Global singleton instance
sse_manager = SSEManager()
