"""Side transcript viewport: scroll rendered rows without moving the composer."""

from bisect import bisect_right
import asyncio
from functools import lru_cache
from types import SimpleNamespace

from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.data_structures import Point
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType
from prompt_toolkit.selection import SelectionState
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


class TranscriptControl(BufferControl):
    """Select read-only output without taking keyboard focus from the composer."""

    def __init__(self, view, buffer, lexer):
        super().__init__(buffer=buffer, lexer=lexer, focusable=False)
        self.view = view
        self.anchor = None

    def mouse_handler(self, event):
        if event.button != MouseButton.LEFT or event.event_type not in (
            MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_MOVE, MouseEventType.MOUSE_UP
        ):
            return NotImplemented
        if self._last_get_processed_line is None:
            return NotImplemented
        column = self._last_get_processed_line(event.position.y).display_to_source(event.position.x)
        index = self.buffer.document.translate_row_col_to_index(event.position.y, column)
        if event.event_type == MouseEventType.MOUSE_DOWN:
            self.anchor = index
            self.view.follow = False
            self.view.copy_status = ""
            self.buffer.exit_selection()
            self.buffer.cursor_position = index
        elif self.anchor is not None:
            self.buffer.cursor_position = index
            self.buffer.selection_state = SelectionState(original_cursor_position=self.anchor)
            if event.event_type == MouseEventType.MOUSE_UP:
                start, end = sorted((self.anchor, index))
                self.anchor = None
                if start != end:
                    self.view.copy_text(self.buffer.text[start:end + 1])
                else:
                    self.buffer.exit_selection()
        self.view.cli._app.invalidate()
        return None


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
        buffer = self.view.transcript.buffer
        selecting = self.content.anchor is not None or buffer.selection_state is not None
        info = self.render_info
        size = self.view.cli._app.output.get_size()
        width = info.window_width if info else max(1, size.columns - 1)
        height = info.window_height if info else max(1, size.rows - 10)
        self._scroll_when_linewrapping(self.content.create_content(width, height), width, height)
        target = (round(self.maximum * fraction) if fraction is not None else
                  self.top + direction * (amount if amount is not None else max(1, height - 1)))
        self._set_top(target)
        self.view.follow = self.top == self.maximum and not selecting
        if not selecting:
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
        self._drag_point = None
        self._edge_timer = None
        self._refresh_selection = False
        self._bounds = None
        self._text_handlers = {}
        super().__init__(children)

    def cancel_drag(self):
        if self._edge_timer is not None:
            self._edge_timer.cancel()
            self._edge_timer = None
        self._drag_point = None
        self._refresh_selection = False
        self.view.transcript.control.anchor = None
        self.dragging_scrollbar = False

    def _select_pointer(self, kind=MouseEventType.MOUSE_MOVE):
        if self._drag_point is None or self._bounds is None:
            return
        left, top, right, bottom = self._bounds
        point = Point(max(left, min(right, self._drag_point.x)),
                      max(top, min(bottom, self._drag_point.y)))
        # Reuse Window's rendered-cell mapping, including wrapping, wide glyphs
        # and styled text. Never interpret screen columns as string offsets.
        self._text_handlers[point.y, point.x](
            MouseEvent(point, kind, MouseButton.LEFT, frozenset()))

    def _edge_direction(self):
        if self._drag_point is None or self._bounds is None:
            return 0
        return (-1 if self._drag_point.y <= self._bounds[1] else
                1 if self._drag_point.y >= self._bounds[3] else 0)

    def _schedule_edge_scroll(self):
        window = self.view.transcript.window
        direction = self._edge_direction()
        can_scroll = window.top > 0 if direction < 0 else window.top < window.maximum
        if (self._edge_timer is None and direction and can_scroll and self.view.visible
                and self.view.transcript.control.anchor is not None
                and self.view.cli._app.is_running):
            self._edge_timer = asyncio.get_running_loop().call_later(.1, self._scroll_edge)

    def _scroll_edge(self):
        self._edge_timer = None
        if (not self.view.cli._app.is_running or not self.view.visible
                or self.view.transcript.control.anchor is None):
            self.cancel_drag()
            return
        direction = self._edge_direction()
        if direction:
            window = self.view.transcript.window
            previous = window.top
            window.move(direction, amount=1)
            # Extend only after repaint, when the cell-to-text mapping is fresh.
            self._refresh_selection = window.top != previous

    def write_to_screen(self, screen, mouse_handlers, write_position, parent_style, erase_bg, z_index):
        super().write_to_screen(screen, mouse_handlers, write_position, parent_style, erase_bg, z_index)
        window = self.view.transcript.window
        area = screen.visible_windows_to_write_positions.get(window)
        if area is not None and area.width > 1 and area.height > 0:
            self._bounds = (area.xpos, area.ypos, area.xpos + area.width - 2,
                            area.ypos + area.height - 1)
            self._text_handlers = {(y, x): mouse_handlers.mouse_handlers[y][x]
                                   for y in range(area.ypos, area.ypos + area.height)
                                   for x in range(area.xpos, area.xpos + area.width - 1)}
            if self._refresh_selection and window.content.anchor is not None:
                self._refresh_selection = False
                self._select_pointer()
            self._schedule_edge_scroll()
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
            if event.event_type == MouseEventType.MOUSE_DOWN:
                self.cancel_drag()
            directions = {MouseEventType.SCROLL_UP: -1, MouseEventType.SCROLL_DOWN: 1}
            if event.event_type in directions:
                if self.view.transcript.control.anchor is not None:
                    self._drag_point = event.position
                    self._refresh_selection = True
                self.view.scroll(directions[event.event_type], amount=3)
                return None
            control = self.view.transcript.control
            if (control.anchor is not None and event.event_type in
                    (MouseEventType.MOUSE_MOVE, MouseEventType.MOUSE_UP)
                    and event.button in (MouseButton.LEFT, MouseButton.NONE)):
                self._drag_point = event.position
                self._select_pointer(event.event_type)
                if event.event_type == MouseEventType.MOUSE_UP:
                    self.cancel_drag()
                else:
                    self._schedule_edge_scroll()
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
