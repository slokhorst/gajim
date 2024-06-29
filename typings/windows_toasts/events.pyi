"""
This type stub file was generated by pyright.
"""

from typing import Optional

from dataclasses import dataclass

from winrt import system

@dataclass
class ToastActivatedEventArgs:
    """
    Wrapper over Windows' ToastActivatedEventArgs to fix an issue with reading user input
    """
    arguments: Optional[str] = ...
    inputs: Optional[dict] = ...
    @classmethod
    def fromWinRt(cls, eventArgs: system.Object) -> ToastActivatedEventArgs:
        ...

class ToastDismissalReason: ...
class ToastDismissedEventArgs: ...
class ToastFailedEventArgs: ...