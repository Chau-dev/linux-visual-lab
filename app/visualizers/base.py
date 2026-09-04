from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.core.events import SystemEvent
from app.models.filesystem_object import FilesystemObject


class BaseVisualizer(QWidget):
    """
    Common contract for all educational visualizers in Linux Visual Learning Lab.

    Visualizers receive domain models (FilesystemObject, TerminalSession)
    and render visual diagrams, state breakdowns, and step-by-step kernel reasoning.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_context: FilesystemObject | None = None

    def set_context(self, fs_object: FilesystemObject | None):
        """
        Update the visualizer with a newly selected or refreshed filesystem object.
        """
        self.current_context = fs_object
        if fs_object is None:
            self.clear_context()
        else:
            self.render_context(fs_object)

    def clear_context(self):
        """
        Reset the visualizer into its empty or neutral state.
        Subclasses should override this to clear UI elements.
        """
        self.current_context = None

    def render_context(self, fs_object: FilesystemObject):
        """
        Render the domain model into visual widgets and explanations.
        Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement render_context.")

    def on_event(self, event: SystemEvent):
        """
        React to live Linux events published via EventBus.
        Default implementation is a no-op; subclasses can override for real-time reactivity.
        """
        pass
