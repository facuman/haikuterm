#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# haikuterm is Copyright (c) 2011 Facundo de Guzmán <facudeguzman@gmail.com>
#
# This file is part of haikuterm.
#
# haikuterm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Foobar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with haikuterm.  If not, see <http://www.gnu.org/licenses/>.
from PyQt4 import QtGui, QtCore
import sys
import emuvt100
import session

# NORMAL, LIGHT/BRIGHT
COLOR_TABLE = [#black
               (QtGui.QColor(0, 0, 0), QtGui.QColor(0, 0, 0)),
               #red
               (QtGui.QColor(205, 0, 0), QtGui.QColor(205, 0, 0)),
               #green
               (QtGui.QColor(0, 205, 0), QtGui.QColor(205, 0, 0)),
               #brown,yellow
               (QtGui.QColor(205, 205, 0), QtGui.QColor(205, 0, 0)),
               #blue
               (QtGui.QColor(0, 0, 238), QtGui.QColor(205, 0, 0)),
               #magenta
               (QtGui.QColor(205, 0, 205), QtGui.QColor(205, 0, 0)),
               #cyan
               (QtGui.QColor(0, 205, 205), QtGui.QColor(205, 0, 0)),
               #gray
               (QtGui.QColor(229, 229, 229), QtGui.QColor(205, 0, 0))]


class HaikutermWidget(QtGui.QFrame):
    def __init__(self, parent=None, app=None):
        super(HaikutermWidget, self).__init__(parent)
        
        self.app = app

        self.ROWS = self.rows = 24
        self.COLS = self.cols = 80

        self._fixed_size = 0
        self.row_spacing = 1
        self.col_spacing = 1

        self.background_color = QtGui.QColor(0, 0, 0)
        self.foreground_color = QtGui.QColor(255, 255, 255)

        self.terminal = None
        self.set_terminal()

        self.setAutoFillBackground(True)
        self.setFocusPolicy(QtCore.Qt.WheelFocus)
        # this is an important optimization, it tells Qt
        # that TerminalDisplay will handle repainting its entire area.
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)

        self.font_height = 1
        self.font_weight = 1
        self.font_width = 1
        self.cell_width = 1
        self.cell_height = 1

        self.screen = {}
        self.screenRend = {}

        self.shell = None

        self.set_default_font()

        self._changes = []

        self.redraw_screen = False

        self.cursor_row = 0
        self.cursor_col = 0
        self.cursor_color = COLOR_TABLE[7][0]
        self.cursor_type = 0

        self.blinking = False
        self.blink = False
        self.blink_timer = QtCore.QTimer()
        self.blink_timer.start(1000)
        self.update_blinking(activate=True)

    def activateWindow(self):
        self.redraw_screen = False
        super(HaikutermWidget, self).activateWindow()

    def update_blinking(self, activate=False):
        if not activate and self.blinking:
            self.disconnect(self.blink_timer, QtCore.SIGNAL("timeout()"))
        else:
            self.connect(self.blink_timer, QtCore.SIGNAL("timeout()"),
                         self.blink_bang)

    def set_cursor_type(self, line=True, block=False):
        if block:
            self.cursor_type = 1
        else:
            self.cursor_type = 0

    def blink_bang(self):
        self.blink = not self.blink
        self.update()

    def set_terminal(self):
        self.terminal = emuvt100.V102Terminal(self.rows, self.cols)
        self.terminal.SetCallback(self.terminal.CALLBACK_SCROLL_UP_SCREEN,
                                  self.update_lines)
        self.terminal.SetCallback(self.terminal.CALLBACK_UPDATE_LINES,
                                  self.update_lines)
        self.terminal.SetCallback(self.terminal.CALLBACK_UPDATE_CURSOR_POS,
                                  self.update_cursor_position)
        self.terminal.SetCallback(self.terminal.CALLBACK_UPDATE_WINDOW_TITLE,
                                  self.set_window_title)
        self.terminal.SetCallback(self.terminal.CALLBACK_UNHANDLED_ESC_SEQ,
                                  self.unhandled_esc_seq)

    def update_cursor_position(self):
        row, col = self.terminal.GetCursorPos()
        self.cursor_row = row
        self.cursor_col = col

    def set_window_title(self, title):
        self.setWindowTitle(title)

    def unhandled_esc_seq(self, key):
        pass

    def set_default_font(self):
        font = QtGui.QFont()
        font.setFamily("Terminus")
        font.setPixelSize(14)
        font.setStyle(font.StyleNormal)
        font.setWeight(font.Normal)
        self.setFont(font)
        self.fontChange(font)

    def print_test_screen(self):
        for line in self.terminal.screen:
            current_line = u"".join([char for char in line])
            print current_line

    def _get_rendition_font(self, rendition):
        font = self.font()
        if rendition.intensity > 0:
            font.setBold(True)
        elif rendition.intensity < 0:
            font.setWeight(font.Light)
        if rendition.italic:
            font.setItalic(True)
        if rendition.underline:
            font.setUnderline(True)
        return font

    def _get_color_from_table(self, color_index):
        return COLOR_TABLE[color_index][0]

    def draw_cursor(self, painter):
        left = self.contentsRect().left()
        top = self.contentsRect().top()

        x = left + self.cursor_col * self.cell_width
        y = top + self.cursor_row * self.cell_height

        rect = QtCore.QRect(QtCore.QPoint(x, y), QtCore.QSize(self.cell_width,
                                                             self.cell_height))
        if self.blink:
            cursor_color = self.cursor_color
        else:
            cursor_color = self.background_color

        if self.cursor_type:
            painter.fillRect(rect, cursor_color)
        else:
            painter.setPen(cursor_color)
            painter.drawLine(QtCore.QPoint(x, y + 2),
                             QtCore.QPoint(x, y + self.cell_height - 1))

    def draw_screen(self, painter):
        left = self.contentsRect().left()
        top = self.contentsRect().top()
        update_char_count = 0
        changes = []
        changes, self._changes = self._changes, changes

        curRendition = emuvt100.Rendition()
        for row, col, char, rendition in changes:
            x = left + col * self.cell_width
            y = top + row * self.cell_height

            if rendition:
                curRendition = rendition

            font = self._get_rendition_font(curRendition)
            fg_color = self._get_color_from_table(curRendition.fg_color)
            bg_color = self._get_color_from_table(curRendition.bg_color)

            rect = QtCore.QRect(QtCore.QPoint(x, y),
                                QtCore.QSize(self.cell_width,
                                             self.cell_height))
            painter.fillRect(rect, bg_color)
            painter.setFont(font)
            painter.setPen(fg_color)
            painter.drawText(rect, QtCore.Qt.AlignCenter, char)
            update_char_count += 1
        self.changes_per_update(painter, update_char_count)

    def changes_per_update(self, painter, update_char_count):
        field_width = 80
        left = self.contentsRect().right() - field_width
        top = self.contentsRect().bottom() - self.cell_height - 5
        update_rect = QtCore.QRect(QtCore.QPoint(left, top),
                                   QtCore.QSize(field_width, self.cell_height))
        painter.fillRect(update_rect, self.background_color)
        painter.setPen(QtCore.Qt.white)
        painter.drawText(QtCore.QPoint(left, top + self.cell_height),
                         "Upd: %s" % update_char_count)

    def update_lines(self):
        for row in self.terminal.GetDirtyLines(self.redraw_screen):
            line = self.terminal.GetLine(row)

            if row not in self.screen:
                self.screen[row] = {}
                self.screenRend[row] = {}
                for col in xrange(len(line)):
                    char = self.terminal.GetChar(row, col)
                    rendition = self.terminal.GetRenditionAlternate(row, col)

                    self.screen[row].setdefault(col, {1:None})
                    self.screen[row][col] = char

                    self.screenRend[row].setdefault(col, {1:None})
                    self.screenRend[row][col] = rendition

                    self._changes.append((row, col, char, rendition))
            else:
                for col in xrange(len(line)):
                    char = self.terminal.GetChar(row, col)
                    rendition = self.terminal.GetRenditionAlternate(row, col)

                    if u"ribadeo" in line and char == u"-":
                        pass

                    if (self.screen[row][col] != char or
                        rendition is None or
                        self.screenRend[row][col] != rendition):

                        self.screen[row][col] = char
                        self.screenRend[row][col] = rendition

                        self._changes.append((row, col, char, rendition))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        if self.redraw_screen:
            painter.fillRect(self.contentsRect(), self.background_color)
        self.draw_screen(painter)
        self.draw_cursor(painter)
        painter.end()
        self.redraw_screen = False

    def fontChange(self, font):
        fm = QtGui.QFontMetrics(font) # QFontMetrics fm(font())
        self.font_height = fm.leading()
        self.row_spacing = fm.lineSpacing()
        for i in xrange(128):
            i = chr(i)
            if not i.isalnum():
                continue
            fw = fm.width(i)
            if self.font_width < fw:
                self.font_width = fw
        if self.font_width > 200: # don't trust unrealistic value, fallback to
                                  # QFontMetrics::maxWidth()
            self.font_width = fm.maxWidth()
        if self.font_width < 1:
            self.font_width = 1
        self.font_width = fm.averageCharWidth()
        self._recalculate_grid_size()
        self.update()

    def _recalculate_grid_size(self):
        if not self.fixed_size:
            self.cell_width = self.font_width  + self.col_spacing
            self.cell_height = self.font_height + self.row_spacing
            self.cols = self.contentsRect().width() / self.cell_width
            self.rows = self.contentsRect().height() / self.cell_height
        else:
            self.cols = self.COLS
            self.rows = self.ROWS
            self.cell_width =  (self.contentsRect().width() / self.COLS +
                                self.col_spacing)
            self.cell_height =  (self.contentsRect().height() / self.ROWS +
                                 self.row_spacing)

        if self.terminal:
            term_rows, term_cols = self.terminal.GetSize()
            if term_rows != self.rows or term_cols != self.cols:
                self.terminal.Resize(self.rows, self.cols)
                self.emit(QtCore.SIGNAL("resize"), self.rows, self.cols)

    def resizeEvent(self, e):
        self._recalculate_grid_size()
        self.redraw_screen = True
        self.screen = {}
        super(HaikutermWidget, self).resizeEvent(e)

    def get_fixed_size(self):
        return self._fixed_size

    def set_fixed_size(self, value):
        self._fixed_size = value
        self._recalculate_grid_size()

    fixed_size = property(get_fixed_size, set_fixed_size)

    def run_shell(self, path):
        self.shell = session.Session(self, path)
        self.connect(self.shell, QtCore.SIGNAL("receive"), self.read_output)
        self.connect(self.shell, QtCore.SIGNAL("done"), self.done)
        self.shell.start()
        self.emit(QtCore.SIGNAL("resize"), self.rows, self.cols)

    def read_output(self, output):
        self.terminal.ProcessInput(output)

        self.update()

    def keyPressEvent(self, event):
        char_ordinal = event.key()

        keystrokes = None

        if char_ordinal == QtCore.Qt.Key_Enter:
            keystrokes = u"\r"
        elif char_ordinal == QtCore.Qt.Key_Tab:
            keystrokes = u"\t"
        elif char_ordinal == QtCore.Qt.Key_Up:
            keystrokes = u"\033[A"
        elif char_ordinal == QtCore.Qt.Key_Down:
            keystrokes = u"\033[B"
        elif char_ordinal == QtCore.Qt.Key_Right:
            keystrokes = u"\033[C"
        elif char_ordinal == QtCore.Qt.Key_Left:
            keystrokes = u"\033[D"

        if keystrokes is not None:
            self.emit(QtCore.SIGNAL("write"), keystrokes)
        else:
            self.emit(QtCore.SIGNAL("write"), event.text())

    def closeEvent(self, event):
        if self.shell:
            self.emit(QtCore.SIGNAL("close_pty"))
        super(HaikutermWidget, self).closeEvent(event)

    def done(self):
        self.close()

if __name__ == '__main__':
    my_app = QtGui.QApplication(sys.argv)

    w = HaikutermWidget(app=my_app)
    w.run_shell("/bin/bash")

    w.show()
    sys.exit(my_app.exec_())




