#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# haikuterm is Copyright (c) 2011 Facundo de Guzmán <facudeguzman@gmail.com>
#
# This file is part of haikuterm.
#
# It's a fork of TermEmulator - Emulator for VT100 terminal programs by
#
# Siva Chandran P
# siva.chandran.p@gmail.com
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
#
# Facundo de Guzmán
# facudeguzman@gmail.com

"""
Emulator for VT100 terminal programs.

This module provides terminal emulation for VT100 terminal programs. It handles
V100 special characters and most important escape sequences. It also handles
graphics rendition which specifies text style(i.e. bold, italics), foreground
color and background color. The handled escape sequences are CUU, CUD, CUF,
CUB, CHA, CUP, ED, EL, VPA and SGR.
"""
import sys

class Rendition(object):
    def __init__(self):
        self.blinking = False
        self.italic = False
        self.underline = False
        self.default_bg_color = 0
        self.bg_color = 0
        self.default_fg_color = 7
        self.fg_color = 7
        self.font = 0
        self.intensity = 0

    def swap_colors(self):
        self.bg_color, self.fg_color = self.fg_color, self.bg_color

    def set_fg_color(self, color=None, xterm=None):
        if color:
            self.fg_color = color
        elif xterm:
            self.fg_color = xterm
        else:
            self.fg_color = self.default_fg_color

    def set_bg_color(self, color=None, xterm=None):
        if color:
            self.bg_color = color
        elif xterm:
            self.bg_color = xterm
        else:
            self.bg_color = self.default_bg_color

    def __eq__(self, other):
        if other is None:
            return False
        return (self.blinking == other.blinking and
                self.italic == other.italic and
                self.underline == other.underline and
                self.bg_color == other.bg_color and
                self.fg_color == other.fg_color and
                self.font == other.font and
                self.intensity == other.intensity)

class V102Terminal:
    __ASCII_NUL = 0     # Null
    __ASCII_BEL = 7     # Bell
    __ASCII_BS = 8      # Backspace
    __ASCII_HT = 9      # Horizontal Tab
    __ASCII_LF = 10     # Line Feed
    __ASCII_VT = 11     # Vertical Tab
    __ASCII_FF = 12     # Form Feed
    __ASCII_CR = 13     # Carriage Return
    __ASCII_XON = 17    # Resume Transmission
    __ASCII_XOFF = 19   # Stop Transmission or Ignore Characters
    __ASCII_ESC = 27    # Escape
    __ASCII_SPACE = 32  # Space
    __ASCII_CSI = 153   # Control Sequence Introducer
    
    __ESCSEQ_CUU = 'A'  # n A: Moves the cursor up n(default 1) times.
    __ESCSEQ_CUD = 'B'  # n B: Moves the cursor down n(default 1) times.
    __ESCSEQ_CUF = 'C'  # n C: Moves the cursor forward n(default 1) times.
    __ESCSEQ_CUB = 'D'  # n D: Moves the cursor backward n(default 1) times.
    
    __ESCSEQ_CHA = 'G'  # n G: Cursor horizontal absolute position. 'n' denotes
                        # the column no(1 based index). Should retain the line 
                        # position.
    
    __ESCSEQ_CUP = 'H'  # n ; m H: Moves the cursor to row n, column m.
                        # The values are 1-based, and default to 1 (top left
                        # corner). 
    
    __ESCSEQ_ED = 'J'   # n J: Clears part of the screen. If n is zero 
                        # (or missing), clear from cursor to end of screen. 
                        # If n is one, clear from cursor to beginning of the 
                        # screen. If n is two, clear entire screen.
    
    __ESCSEQ_EL = 'K'   # n K: Erases part of the line. If n is zero 
                        # (or missing), clear from cursor to the end of the
                        # line. If n is one, clear from cursor to beginning of 
                        # the line. If n is two, clear entire line. Cursor 
                        # position does not change.
    
    __ESCSEQ_VPA = 'd'  # n d: Cursor vertical absolute position. 'n' denotes
                        # the line no(1 based index). Should retain the column 
                        # position.
    
    __ESCSEQ_SGR = 'm'  # n [;k] m: Sets SGR (Select Graphic Rendition) 
                        # parameters. After CSI can be zero or more parameters
                        # separated with ;. With no parameters, CSI m is treated
                        # as CSI 0 m (reset / normal), which is typical of most
                        # of the ANSI codes.
    
    RENDITION_STYLE_BOLD = 1
    RENDITION_STYLE_DIM = 2
    RENDITION_STYLE_ITALIC = 4
    RENDITION_STYLE_UNDERLINE = 8
    RENDITION_STYLE_SLOW_BLINK = 16
    RENDITION_STYLE_FAST_BLINK = 32
    RENDITION_STYLE_INVERSE = 64
    RENDITION_STYLE_HIDDEN = 128
    
    CALLBACK_SCROLL_UP_SCREEN = 1
    CALLBACK_UPDATE_LINES = 2
    CALLBACK_UPDATE_CURSOR_POS = 3
    CALLBACK_UPDATE_WINDOW_TITLE = 4
    CALLBACK_UNHANDLED_ESC_SEQ = 5
    
    def __init__(self, rows, cols):
        """
        Initializes the terminal with specified rows and columns. User can 
        resize the terminal any time using Resize method. By default the screen
        is cleared(filled with blank spaces) and cursor positioned in the first
        row and first column.
        """
        self.cols = cols
        self.rows = rows
        self.curX = 0
        self.curY = 0
        self.ignoreChars = False
        
        # special character handlers
        self.charHandlers = {
                             self.__ASCII_NUL:self.__OnCharIgnore,
                             self.__ASCII_BEL:self.__OnCharIgnore,
                             self.__ASCII_BS:self.__OnCharBS,
                             self.__ASCII_HT:self.__OnCharHT,
                             self.__ASCII_LF:self.__OnCharLF,
                             self.__ASCII_VT:self.__OnCharLF,
                             self.__ASCII_FF:self.__OnCharLF,
                             self.__ASCII_CR:self.__OnCharCR,
                             self.__ASCII_XON:self.__OnCharXON,
                             self.__ASCII_XOFF:self.__OnCharXOFF,
                             self.__ASCII_ESC:self.__OnCharESC,
                             self.__ASCII_CSI:self.__OnCharCSI,
                            }
        
        # escape sequence handlers
        self.escSeqHandlers = {
                               self.__ESCSEQ_CUU:self.__OnEscSeqCUU,
                               self.__ESCSEQ_CUD:self.__OnEscSeqCUD,
                               self.__ESCSEQ_CUF:self.__OnEscSeqCUF,
                               self.__ESCSEQ_CUB:self.__OnEscSeqCUB,
                               self.__ESCSEQ_CHA:self.__OnEscSeqCHA,
                               self.__ESCSEQ_CUP:self.__OnEscSeqCUP,
                               self.__ESCSEQ_ED:self.__OnEscSeqED,
                               self.__ESCSEQ_EL:self.__OnEscSeqEL,
                               self.__ESCSEQ_VPA:self.__OnEscSeqVPA,
                               self.__ESCSEQ_SGR:self.__OnEscSeqSGR,
                              }

        # terminal screen, its a list of string in which each string always
        # holds self.cols characters. If the screen doesn't contain any 
        # character then it'll blank space
        self.screen = []

        # terminal screen rendition, its a list of current of long. The first
        # 8 bits of the long holds the rendition style/attribute(i.e. bold,
        # italics and etc). The next 4 bits specifies the foreground color and
        # next 4 bits for background
        self.scrRendition = []


        # current rendition
        self.curRendition = Rendition()
        
        # list of dirty lines since last call to GetDirtyLines
        self.isLineDirty = []
        
        for i in range(rows):
            line = []
            rendition = []
            
            for j in range(cols):
                line.append(u' ')
                rendition.append(None)

            self.screen.append(line)
            self.scrRendition.append(rendition)
            self.isLineDirty.append(False)

        # initializes callbacks
        self.callbacks = {
                          self.CALLBACK_SCROLL_UP_SCREEN: None,
                          self.CALLBACK_UPDATE_LINES: None,
                          self.CALLBACK_UPDATE_CURSOR_POS: None,
                          self.CALLBACK_UNHANDLED_ESC_SEQ: None,
                          self.CALLBACK_UPDATE_WINDOW_TITLE: None,
                         }

        # unparsed part of last input
        self.unparsedInput = None

    def GetRawScreen(self):
        """
        Returns the screen as a list of strings. The list will have rows no. of
        strings and each string will have columns no. of characters. Blank
        space used represents no character.
        """
        return self.screen

    def GetRawScreenRendition(self):
        """
        Returns the screen as a list of current of long. The list will have
        rows no. of current and each current will have columns no. of longs.
        The first 8 bits of long represents rendition style like bold, italics
        and etc. The next 4 bits represents foreground color and next 4 bits
        for background color.
        """
        return self.scrRendition

    def GetRows(self):
        """
        Returns no. rows in the terminal
        """
        return self.rows

    def GetCols(self):
        """
        Returns no. cols in the terminal
        """
        return self.cols

    def GetSize(self):
        """
        Returns terminal rows and cols as tuple
        """
        return self.rows, self.cols

    def Resize(self, rows, cols):
        """
        Resizes the terminal to specified rows and cols.
        - If the new no. rows is less than existing no. rows then existing rows
          are deleted at top.
        - If the new no. rows is greater than existing no. rows then
          blank rows are added at bottom.
        - If the new no. cols is less than existing no. cols then existing cols
          are deleted at right.
        - If the new no. cols is greater than existing no. cols then new cols
          are added at right.
        """
        if rows < self.rows:
            # remove rows at top
            for i in range(self.rows - rows):
                self.isLineDirty.pop(0)
                self.screen.pop(0)
                self.scrRendition.pop(0)

        elif rows > self.rows:
            # add blank rows at bottom
            for i in range(rows - self.rows):
                line = []
                rendition = []

                for j in range(self.cols):
                    line.append(u' ')
                    rendition.append(None)
                
                self.screen.append(line)
                self.scrRendition.append(rendition)
                self.isLineDirty.append(False)

        self.rows = rows

        if cols < self.cols:
            # remove cols at right
            for i in range(self.rows):
                self.screen[i] = self.screen[i][:cols - self.cols]
                for j in range(self.cols - cols):
                    self.scrRendition[i].pop(len(self.scrRendition[i]) - 1)
        elif cols > self.cols:
            # add cols at right
            for i in range(self.rows):
                for j in range(cols - self.cols):
                    self.screen[i].append(u' ')
                    self.scrRendition[i].append(None)

        self.cols = cols
        
    def GetCursorPos(self):
        """
        Returns cursor position as tuple
        """
        return self.curY, self.curX
    
    def Clear(self):
        """
        Clears the entire terminal screen
        """
        ClearRect(0, 0, self.rows - 1, self.cols - 1)
        
    def ClearRect(self, startRow, startCol, endRow, endCol):
        """
        Clears the terminal screen starting from startRow and startCol to
        endRow and EndCol.
        """
        if startRow < 0:
            startRow = 0
        elif startRow >= self.rows:
            startRow = self.rows - 1
            
        if startCol < 0:
            startCol = 0
        elif startCol >= self.cols:
            startCol = self.cols - 1
            
        if endRow < 0:
            endRow = 0
        elif endRow >= self.rows:
            endRow = self.rows - 1
            
        if endCol < 0:
            endCol = 0
        elif endCol >= self.cols:
            endCol = self.cols - 1
            
        if startRow > endRow:
            startRow, endRow = endRow, startRow
            
        if startCol > endCol:
            startCol, endCol = endCol, startCol
        
        for i in range(startRow, endRow + 1):
            start = 0
            end = self.cols - 1
            
            if i == startRow:
                start = startCol
            elif i == endRow:
                end = endCol
                
            for j in range(start, end + 1):
                self.screen[i][j] = u' '
                self.scrRendition[i][j] = None
                
            if end + 1 > start:
                self.isLineDirty[i] = True 

    def GetChar(self, row, col):
        return self.screen[row][col]

    def GetRendition(self, row, col):
        return self.scrRendition[row][col]

    def GetLine(self, lineno):
        """
        Returns the terminal screen line specified by lineno. The line is
        returned as string, blank space represents empty character. The lineno
        should be in the range 0..rows - 1
        """
        if lineno < 0 or lineno >= self.rows:
            return None

        return u"".join(self.screen[lineno])

    def GetLines(self):
        """
        Returns terminal screen lines as a list, same as GetScreen
        """
        lines = []
        
        for i in range(self.rows):
            lines.append(self.screen[i].tostring())
        
        return lines
        
    def GetLinesAsText(self):
        """
        Returns the entire terminal screen as a single big string. Each row
        is seperated by \\n and blank space represents empty character.
        """
        text = u""
        
        for i in range(self.rows):
            text += self.screen[i].tostring()
            text += u'\n'
        
        text = text.rstrip('\n') # removes leading new lines
        
        return text
    
    def GetDirtyLines(self, get_all=False):
        """
        Returns list of dirty lines(line nos) since last call to GetDirtyLines.
        The line no will be 0..rows - 1.
        """
        dirtyLines = []
        
        for i in range(self.rows):
            if self.isLineDirty[i] or get_all:
                dirtyLines.append(i)
                self.isLineDirty[i] = False
        
        return dirtyLines

    def SetCallback(self, event, func):
        """
        Sets callback function for the specified event. The event should be
        any one of the following. None can be passed as callback function to
        reset the callback.
        
        CALLBACK_SCROLL_UP_SCREEN
            Called before scrolling up the terminal screen.
                        
        CALLBACK_UPDATE_LINES
            Called when ever some lines need to be updated. Usually called
            before leaving ProcessInput and before scrolling up the
            terminal screen.
            
        CALLBACK_UPDATE_CURSOR_POS
            Called to update the cursor position. Usually called before leaving
            ProcessInput.
            
        CALLBACK_UPDATE_WINDOW_TITLE
            Called when ever a window title escape sequence encountered. The
            terminal window title will be passed as a string.
        
        CALLBACK_UNHANDLED_ESC_SEQ
            Called when ever a unsupported escape sequence encountered. The
            unhandled escape sequence(escape sequence character and it 
            parameters) will be passed as a string.
        """
        self.callbacks[event] = func

    def ProcessInput(self, text):
        """
        Processes the given input text. It detects V100 escape sequences and
        handles it. Any partial unparsed escape sequences are stored internally
        and processed along with next input text. Before leaving, the function
        calls the callbacks CALLBACK_UPDATE_LINE and CALLBACK_UPDATE_CURSOR_POS
        to update the pre   vious lines and cursor position respectively.
        """
        if text is None:
            return

        if self.unparsedInput is not None:
            text = self.unparsedInput + text
            self.unparsedInput = None

        textlen = len(text)

        index = 0
        while index < textlen:
            char = text[index]
            char_ordinal = ord(char)

            if self.ignoreChars:
                index += 1
                continue

            if char_ordinal in self.charHandlers.keys():
                index = self.charHandlers[char_ordinal](text, index)
            else:
                self.__PushChar(char)

                index += 1

        # update the dirty lines
        if self.callbacks[self.CALLBACK_UPDATE_LINES] is not None:
            self.callbacks[self.CALLBACK_UPDATE_LINES]()

        # update cursor position
        if self.callbacks[self.CALLBACK_UPDATE_CURSOR_POS] is not None:
            self.callbacks[self.CALLBACK_UPDATE_CURSOR_POS]()

    def ScrollUp(self):
        """
        Scrolls up the terminal screen by one line. The callbacks
        CALLBACK_UPDATE_LINES and CALLBACK_SCROLL_UP_SCREEN are called before
        scrolling the screen.
        """
        # update the dirty lines
        if self.callbacks[self.CALLBACK_UPDATE_LINES] is not None:
            self.callbacks[self.CALLBACK_UPDATE_LINES]()
        
        # scrolls up the screen
        if self.callbacks[self.CALLBACK_SCROLL_UP_SCREEN] is not None:
            self.callbacks[self.CALLBACK_SCROLL_UP_SCREEN]()
            
        line = self.screen.pop(0)
        for i in range(self.cols):
            line[i] = u' '
        self.screen.append(line)
        
        rendition = self.scrRendition.pop(0)
        for i in range(self.cols):
            rendition[i] = None
        self.scrRendition.append(rendition)
           
    def Dump(self, file=sys.stdout):
        """
        Dumps the entire terminal screen into the given file/stdout
        """
        for i in range(self.rows):
            file.write(self.screen[i].tostring())
            file.write("\n")

    def __NewLine(self):
        """
        Moves the cursor to the next line, if the cursor is already at the
        bottom row then scrolls up the screen.
        """
        self.curX = 0
        if self.curY + 1 < self.rows:
            self.curY += 1
        else:
            self.ScrollUp()
        
    def __PushChar(self, ch):
        """
        Writes the character(ch) into current cursor position and advances
        cursor position.
        """
        if self.curX >= self.cols:
            self.__NewLine()

        self.screen[self.curY][self.curX] = ch
        self.scrRendition[self.curY][self.curX] = self.curRendition
        self.curX += 1
        
        self.isLineDirty[self.curY] = True

    def __ParseEscSeq(self, text, index):
        """
        Parses escape sequence from the input and returns the index after escape
        sequence, the escape sequence character and parameter for the escape
        sequence
        """
        textlen = len(text)
        interChars = None
        while index < textlen:
            char = text[index]
            char_ordinal = ord(char)
            
            if char_ordinal >= 32 and char_ordinal <= 63:
                # intermediate char (32 - 47)
                # parameter chars (48 - 63)
                if interChars is None:
                    interChars = char
                else:
                    interChars += char
            elif char_ordinal >= 64 and char_ordinal <= 125:
                # final char
                return index + 1, chr(char_ordinal), interChars
            else:
                print "Unexpected characters in escape sequence ", char
            
            index += 1
        
        # the escape sequence is not complete, inform this to caller by giving
        # '?' as final char
        return index, '?', interChars
    
    def __HandleEscSeq(self, text, index):
        """
        Tries to parse escape sequence from input and if its not complete then
        puts it in unparsedInput and process it when the ProcessInput called
        next time.
        """
        if text[index] == '[':
            index += 1
            index, finalChar, interChars = self.__ParseEscSeq(text, index)
            
            if finalChar == '?':
                self.unparsedInput = "\033["
                if interChars is not None:
                    self.unparsedInput += interChars
            elif finalChar in self.escSeqHandlers.keys():
                self.escSeqHandlers[finalChar](interChars)
            else:
                escSeq = ""
                if interChars is not None:
                    escSeq += interChars
                                    
                escSeq += finalChar
                    
                if self.callbacks[self.CALLBACK_UNHANDLED_ESC_SEQ] is not None:
                    self.callbacks[self.CALLBACK_UNHANDLED_ESC_SEQ](escSeq)
            
        elif text[index] == ']':
            textlen = len(text)
            if index + 2 < textlen:
                if text[index + 1] == '0' and text[index + 2] == ';':
                    # parse title, terminated by bell char(\007)
                    index += 3 # ignore '0' and ';'
                    start = index
                    while index < textlen:
                        if ord(text[index]) == self.__ASCII_BEL:
                            break
                        
                        index += 1
                    
                    self.__OnEscSeqTitle(text[start:index])
                
        return index

    def __OnCharBS(self, text, index):
        """
        Handler for backspace character
        """
        if self.curX > 0:
            self.curX -= 1
            
        return index + 1
    
    def __OnCharHT(self, text, index):
        """
        Handler for horizontal tab character
        """
        while True:
            self.curX += 1
            if not self.curX % 8:
                break
        return index + 1
    
    def __OnCharLF(self, text, index):
        """
        Handler for line feed character
        """
        self.__NewLine()
        return index + 1
    
    def __OnCharCR(self, text, index):
        """
        Handler for carriage return character
        """
        self.curX = 0
        return index + 1
    
    def __OnCharXON(self, text, index):
        """
        Handler for XON character
        """
        self.ignoreChars = False
        return index + 1
    
    def __OnCharXOFF(self, text, index):
        """
        Handler for XOFF character
        """        
        self.ignoreChars = True
        return index + 1

    def __OnCharESC(self, text, index):
        """
        Handler for escape character
        """        
        index += 1
        if index < len(text):
            index = self.__HandleEscSeq(text, index)
        
        return index
    
    def __OnCharCSI(self, text, index):
        """
        Handler for control sequence intruducer(CSI) character
        """        
        index += 1
        index = self.__HandleEscSeq(text, index)
        return index

    def __OnCharIgnore(self, text, index):
        """
        Dummy handler for unhandler characters
        """
        return index + 1
    
    def __OnEscSeqTitle(self, params):
        """
        Handler for window title escape sequence 
        """
        if self.callbacks[self.CALLBACK_UPDATE_WINDOW_TITLE] is not None:
            self.callbacks[self.CALLBACK_UPDATE_WINDOW_TITLE](params)
    
    def __OnEscSeqCUU(self, params):
        """
        Handler for escape sequence CUU 
        """
        n = 1
        if params is not None:
            n = int(params)
            
        self.curY -= n
        if self.curY < 0:
            self.curY = 0
        
    def __OnEscSeqCUD(self, params):
        """
        Handler for escape sequence CUD 
        """
        n = 1
        if params is not None:
            n = int(params)
            
        self.curY += n
        if self.curY >= self.rows:
            self.curY = self.rows - 1
        
    def __OnEscSeqCUF(self, params):
        """
        Handler for escape sequence CUF 
        """
        n = 1
        if params is not None:
            n = int(params)
            
        self.curX += n
        if self.curX >= self.cols:
            self.curX = self.cols - 1

    def __OnEscSeqCUB(self, params):
        """
        Handler for escape sequence CUB 
        """
        n = 1
        if params is not None:
            n = int(params)
            
        self.curX -= n
        if self.curX < 0:
            self.curX = 0

    def __OnEscSeqCHA(self, params):
        """
        Handler for escape sequence CHA 
        """
        if params is None:
            print "WARNING: CHA without parameter"
            return
        
        col = int(params)
        
        # convert it to zero based index
        col -= 1
        if col >= 0 and col < self.cols:
            self.curX = col
        else:
            print "WARNING: CHA column out of boundary"

    def __OnEscSeqCUP(self, params):
        """
        Handler for escape sequence CUP 
        """
        y = 0
        x = 0
        
        if params is not None:
            values = params.split(';')
            if len(values) == 2:
                y = int(values[0]) - 1
                x = int(values[1]) - 1
            else:
                print "WARNING: escape sequence CUP has invalid parameters"
                return 
        
        if x < 0:
            x = 0
        elif x >= self.cols:
            x = self.cols - 1
            
        if y < 0:
            y = 0
        elif y >= self.rows:
            y = self.rows - 1
        
        self.curX = x
        self.curY = y
        
    def __OnEscSeqED(self, params):
        """
        Handler for escape sequence ED 
        """
        n = 0
        if params is not None:
            n = int(params)
        
        if not n:
            self.ClearRect(self.curY, self.curX, self.rows - 1, self.cols - 1)
        elif n == 1:
            self.ClearRect(0, 0, self.curY, self.curX)
        elif n == 2:
            self.ClearRect(0, 0, self.rows - 1, self.cols - 1)
        else:
            print "WARNING: escape sequence ED has invalid parameter"
            
    def __OnEscSeqEL(self, params):
        """
        Handler for escape sequence EL
        """
        n = 0
        if params is not None:
            n = int(params)
        
        if not n:
            self.ClearRect(self.curY, self.curX, self.curY, self.cols - 1)
        elif n == 1:
            self.ClearRect(self.curY, 0, self.curY, self.curX)
        elif n == 2:
            self.ClearRect(self.curY, 0, self.curY, self.cols - 1)
        else:
            print "WARNING: escape sequence EL has invalid parameter"

    def __OnEscSeqVPA(self, params):
        """
        Handler for escape sequence VPA
        """
        if params is None:
            print "WARNING: VPA without parameter"
            return
        
        row = int(params)
        
        # convert it to zero based index
        row -= 1
        if row >= 0 and row < self.rows:
            self.curY = row
        else:
            print "WARNING: VPA line no. out of boundary"

    def __OnEscSeqSGR(self, params):
        """
        Handler for escape sequence SGR
        """
        if params is not None:
            renditions = params.split(';')
            for rendition in renditions:
                irendition = int(rendition)

                if not irendition:
                #0 	Reset / Normal 	all attributes off
                    self.curRendition = Rendition()
                elif irendition == 1:
                #1 	Bright (increased intensity) or Bold
                    self.curRendition.intensity += 1
                elif irendition == 2:
                    self.curRendition.intensity -= 1

                #2 	Faint (decreased intensity) 	not widely supported

                elif irendition == 3:
                #3 	Italic: on 	not widely supported. Sometimes treated as
                # inverse.
                    self.curRendition.italic = True
                elif irendition == 4:
                #4 	Underline: Single
                    self.curRendition.underline = True
                elif irendition in (5,6):
                #5 	Blink: Slow 	less than 150 per minute
                #6 	Blink: Rapid 	MS-DOS ANSI.SYS; 150 per minute or more;
                # not widely supported
                    self.curRendition.blinking = True
                elif irendition == 7:
                #7 	Image: Negative 	inverse or reverse; swap foreground
                # and background
                    self.curRendition.swap_colors()

                #8 	Conceal 	not widely supported
                #9 	Crossed-out 	Characters legible, but marked for
                # deletion. Not widely supported.

                elif irendition >= 10 and irendition <= 19:
                #10 	Primary(default) font
                #11–19 	n-th alternate font 	Select the n-th alternate
                # font. 14 being the fourth alternate font, up to 19 being the
                # 9th alternate font.
                    self.curRendition.font = irendition - 10

                #20 	Fraktur hardly ever supported
                #21 	Bright/Bold: off or Underline: Double 	bold off not
                # widely supported, double underline hardly ever

                elif irendition == 22:
                #22 	Normal color or intensity 	neither bright, bold nor
                # faint
                    self.curRendition.intensity = 0
                elif irendition == 23:
                #23 	Not italic, not Fraktur
                    self.curRendition.italic = False
                elif irendition == 24:
                #24 	Underline: None 	not singly or doubly underlined
                    self.curRendition.underline = False
                elif irendition == 25:
                #25 	Blink: off
                    self.curRendition.blinking = False

                #26 	Reserved
                #27 	Image: Positive
                #28 	Reveal 	conceal off
                #29 	Not crossed out

                elif irendition >= 30 and irendition <= 37:
                #30–37 	Set text color 	30 + x, where x is from the color table
                # below
                    self.curRendition.set_fg_color(color=irendition - 30)

                #elif irendition == 38:
                #38 	Set xterm-256 text color[dubious – discuss] 	next
                # arguments are 5;x where x is color index (0..255)
                    #self.curRendition.set_fg_color(xterm=irendition)

                elif irendition == 39:
                #39 	Default text color 	implementation defined (according
                # to standard)
                    self.curRendition.set_fg_color()

                elif irendition >= 40 and irendition <= 47:
                #40–47 	Set background color 	40 + x, where x is from the
                # color table below
                    self.curRendition.set_bg_color(color=irendition - 40)

                #elif irendition == 48:
                #48 	Set xterm-256 background color 	next arguments are 5;x
                # where x is color index (0..255)
                    #self.curRendition.set_bg_color(xterm=irendition)
                    #pass

                elif irendition == 49:
                #49 	Default background color 	implementation defined
                # (according to standard)
                    self.curRendition.set_bg_color()

                #50 	Reserved
                #51 	Framed
                #52 	Encircled
                #53 	Overlined
                #54 	Not framed or encircled
                #55 	Not overlined
                #56–59 	Reserved
                #60 	ideogram underline or right side line 	hardly ever
                # supported

                #61 	ideogram double underline or double line on the right
                # side 	hardly ever supported

                #62 	ideogram overline or left side line 	hardly ever
                # supported

                #63 	ideogram double overline or double line on the left
                # side 	hardly ever supported

                #64 	ideogram stress marking 	hardly ever supported
                #90–99 	Set foreground color, high intensity 	aixterm (not
                # in standard)

                #100–109 	Set background color, high intensity 	aixterm
                # (not in standard)

                else:
                    print "'%s' not supported" % irendition
