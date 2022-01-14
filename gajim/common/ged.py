# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import Callable

import logging
import traceback
import inspect

from nbxmpp import NodeProcessed

from gajim.common import app
from gajim.common.events import ApplicationEvent

log = logging.getLogger('gajim.c.ged')

PRECORE = 10
CORE = 20
POSTCORE = 30
PREGUI = 40
PREGUI1 = 50
GUI1 = 60
POSTGUI1 = 70
PREGUI2 = 80
GUI2 = 90
POSTGUI2 = 100
POSTGUI = 110


HandlerFuncT = Callable[[Any], Any]
EventHandlerT = tuple[str, int, HandlerFuncT]


class GlobalEventsDispatcher:

    def __init__(self):
        self.handlers: dict[str, list[tuple[int, HandlerFuncT]]] = {}

    def register_event_handler(self,
                               event_name: str,
                               priority: int,
                               handler: HandlerFuncT) -> None:

        if event_name in self.handlers:
            handlers_list = self.handlers[event_name]
            i = 0
            for i, handler_tuple in enumerate(handlers_list):
                if priority < handler_tuple[0]:
                    break
            else:
                # no event with smaller prio found, put it at the end
                i += 1

            handlers_list.insert(i, (priority, handler))
        else:
            self.handlers[event_name] = [(priority, handler)]

    def remove_event_handler(self,
                             event_name: str,
                             priority: int,
                             handler: HandlerFuncT) -> None:

        if event_name in self.handlers:
            try:
                self.handlers[event_name].remove((priority, handler))
            except ValueError as error:
                log.warning(
                    '''Function (%s) with priority "%s" never
                    registered as handler of event "%s". Couldn\'t remove.
                    Error: %s''', handler, priority, event_name, error)

    def raise_event(self, event_obj: ApplicationEvent) -> Any:
        event_name = event_obj.name
        log.debug('Raise event: %s', event_name)
        if event_name in self.handlers:
            node_processed = False
            # Iterate over a copy of the handlers list, so while iterating
            # the original handlers list can be modified
            for _priority, handler in list(self.handlers[event_name]):
                try:
                    if inspect.ismethod(handler):
                        log.debug('Call handler %s on %s',
                                  handler.__name__,
                                  handler.__self__)
                    else:
                        log.debug('Call handler %s', handler.__name__)
                    if handler(event_obj):
                        return True
                except NodeProcessed:
                    node_processed = True
                except Exception:
                    log.error('Error while running an event handler: %s',
                              handler)
                    traceback.print_exc()
            if node_processed:
                raise NodeProcessed


class EventHelper:
    def __init__(self):
        self.__event_handlers: list[EventHandlerT] = []

    def register_event(self,
                       event_name: str,
                       priority: int,
                       handler: HandlerFuncT) -> None:

        self.__event_handlers.append((event_name, priority, handler))
        app.ged.register_event_handler(event_name, priority, handler)

    def register_events(self, events: list[EventHandlerT]) -> None:
        for handler in events:
            self.__event_handlers.append(handler)
            app.ged.register_event_handler(*handler)

    def unregister_event(self,
                         event_name: str,
                         priority: int,
                         handler: HandlerFuncT) -> None:

        self.__event_handlers.remove((event_name, priority, handler))
        app.ged.register_event_handler(event_name, priority, handler)

    def unregister_events(self) -> None:
        for handler in self.__event_handlers:
            app.ged.remove_event_handler(*handler)
        self.__event_handlers.clear()
