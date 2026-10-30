"""Side transcript viewport: scroll rendered rows without moving the composer."""

from bisect import bisect_right
from functools import lru_cache
from types import SimpleNamespace

from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.mouse_events import MouseButton, MouseEventType
from prompt_toolkit.utils import get_cwidth


@lru_cache(maxsize=4096)
def _wrapped_height(text, width):
    # Match Window's character wrapping, including a wide glyph that cannot fit
    # in the final single cell of a row (total_width / width undercounts those).
    rows, column = 1, 0
    for character in text:
        cells = max(0, get_cwidth(character))
        if column + cells > width:
            rows += 1
            column = 0
        column += cells
    return rows


class TranscriptWindow(Window):
    def __init__(self, view, control):
        self.view = view
        self.row_offsets = [0, 1]
        self.top = self.maximum = 0
        super().__init__(control, wrap_lines=True, always_hide_cursor=True,
                         right_margins=[_TranscriptScrollbar(self)])

    def _scroll_when_linewrapping(self, ui_content, width, height):
        # Window's normal scrolling follows a text-editing cursor. A transcript
        # instead owns its viewport; a single log line can span many screen rows.
        offsets = [0]
        for row in range(ui_content.line_count):
            text = ''.join(fragment[1] for fragment in ui_content.get_line(row)
                           if '[ZeroWidthEscape]' not in fragment[0])
            offsets.append(offsets[-1] + _wrapped_height(text, max(1, width)))
        self.row_offsets = offsets
        self.maximum = max(0, offsets[-1] - height)
        anchor = min(self.vertical_scroll, len(offsets) - 2)
        top = offsets[anchor] + min(self.vertical_scroll_2, offsets[anchor + 1] - offsets[anchor] - 1)
        self._set_top(self.maximum if self.view.follow else top)
        self.horizontal_scroll = 0

    def _set_top(self, top):
        self.top = max(0, min(self.maximum, top))
        self.vertical_scroll = min(len(self.row_offsets) - 2, bisect_right(self.row_offsets, self.top) - 1)
        self.vertical_scroll_2 = self.top - self.row_offsets[self.vertical_scroll]

    def move(self, direction, amount=None, *, fraction=None):
        info = self.render_info
        size = self.view.cli._app.output.get_size()
        width = info.window_width if info else max(1, size.columns - 1)
        height = info.window_height if info else max(1, size.rows - 10)
        self._scroll_when_linewrapping(self.content.create_content(width, height), width, height)
        target = (round(self.maximum * fraction) if fraction is not None else
                  self.top + direction * (amount if amount is not None else max(1, height - 1)))
        self._set_top(target)
        self.view.follow = self.top == self.maximum
        buffer = self.view.transcript.buffer
        buffer.cursor_position = (len(buffer.text) if self.view.follow else
                                  buffer.document.translate_row_col_to_index(self.vertical_scroll, 0))
        self.view.cli._app.invalidate()


class _TranscriptScrollbar(ScrollbarMargin):
    def __init__(self, window):
        super().__init__(display_arrows=True)
        self.window = window

    def create_margin(self, window_render_info, width, height):
        # The stock margin counts logical lines; its thumb must use the same
        # wrapped-row coordinates as the viewport and mouse drag handler.
        info = SimpleNamespace(content_height=self.window.row_offsets[-1], window_height=height,
                               displayed_lines=range(min(height, self.window.row_offsets[-1])),
                               vertical_scroll=self.window.top)
        return super().create_margin(info, width, height)


class SideScrollFrame(HSplit):
    def __init__(self, view, children):
        self.view = view
        self.dragging_scrollbar = False
        super().__init__(children)

    def write_to_screen(self, screen, mouse_handlers, write_position, parent_style, erase_bg, z_index):
        super().write_to_screen(screen, mouse_handlers, write_position, parent_style, erase_bg, z_index)
        # The wheel must work over the composer, blank rows and scrollbar too.
        # Wrap the normal handlers so clicks/selections keep their usual behavior.
        wrapped = {}
        for y in range(write_position.ypos, write_position.ypos + write_position.height):
            row = mouse_handlers.mouse_handlers[y]
            for x in range(write_position.xpos, write_position.xpos + write_position.width):
                original = row[x]
                if original not in wrapped:
                    wrapped[original] = self._handler(original, write_position)
                row[x] = wrapped[original]

    def _handler(self, original, position):
        def handle(event):
            directions = {MouseEventType.SCROLL_UP: -1, MouseEventType.SCROLL_DOWN: 1}
            if event.event_type in directions:
                self.view.scroll(directions[event.event_type], amount=3)
                return None
            window = self.view.transcript.window
            info = window.render_info
            # Header occupies one row; the transcript's margin is the rightmost column.
            relative_y = event.position.y - position.ypos - 1
            over_bar = (info is not None and 0 <= relative_y < info.window_height
                        and event.position.x == position.xpos + position.width - 1)
            if event.event_type == MouseEventType.MOUSE_UP:
                was_dragging = self.dragging_scrollbar
                self.dragging_scrollbar = False
                if was_dragging:
                    return None
            if event.button == MouseButton.LEFT and info is not None:
                if over_bar and event.event_type == MouseEventType.MOUSE_DOWN:
                    if relative_y in (0, info.window_height - 1):
                        self.view.scroll(-1 if relative_y == 0 else 1, amount=1)
                        return None
                    self.dragging_scrollbar = True
                if self.dragging_scrollbar and event.event_type in (MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_MOVE):
                    fraction = max(0, min(1, (relative_y - 1) / max(1, info.window_height - 3)))
                    window.move(0, fraction=fraction)
                    return None
            return original(event)
        return handle
