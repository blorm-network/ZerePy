from typing import Callable, Dict, List
from dataclasses import dataclass
import asyncio
import logging

@dataclass
class Event:
    """Event class for message passing between components"""
    name: str
    data: dict
    source: str

class EventBus:
    """Central event bus for managing event subscriptions and publishing"""
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._logger = logging.getLogger("event_bus")

    async def publish(self, event: Event):
        """
        Publish an event to all subscribers
        
        Args:
            event: Event object containing name, data, and source
        """
        if event.name in self._subscribers:
            for callback in self._subscribers[event.name]:
                try:
                    await callback(event)
                except Exception as e:
                    self._logger.error(f"Error in event handler for {event.name}: {e}")
                    # Continue processing other callbacks even if one fails
                    continue

    def subscribe(self, event_name: str, callback: Callable):
        """
        Subscribe to an event
        
        Args:
            event_name: Name of the event to subscribe to
            callback: Async callback function to handle the event
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable):
        """
        Unsubscribe from an event
        
        Args:
            event_name: Name of the event to unsubscribe from
            callback: Callback function to remove
        """
        if event_name in self._subscribers and callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)
            if not self._subscribers[event_name]:
                del self._subscribers[event_name]
