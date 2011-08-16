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
import codecs
from errno import EAGAIN
import os
from PyQt4 import QtCore
import time
import fcntl
import ptty

class Session(QtCore.QThread):
    def __init__(self, parent, cmd_path):
        super(Session, self).__init__()

        self._parent = parent
        self.connect(parent, QtCore.SIGNAL("write"), self.write)
        self.connect(parent, QtCore.SIGNAL("resize"), self.resize)
        self.connect(parent, QtCore.SIGNAL("close_pty"), self.close_pty)

        self.buffer_size = 16384

        self.cmd_path = cmd_path
        self.stream = ptty.spawn(cmd_path)

        # Set child descriptor non blocking
        fl = fcntl.fcntl(self.stream.fileno(), fcntl.F_GETFL)
        fcntl.fcntl(self.stream.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK )

        self.linebuffer = u""
        self.charbuffer = u""
        self.bytebuffer = ""

        #self.stream.setecho(False)
        self.notifier = QtCore.QSocketNotifier(self.stream.fileno(),
                                               QtCore.QSocketNotifier.Read)
        self.utf8_child = codecs.getreader('utf8')(self.stream)
        self._parent.app.connect(self.notifier,
                                 QtCore.SIGNAL('activated(int)'),
                                 self.get_input)

    def get_input(self, fd):
        self._parent.app.disconnect(self.notifier,
                                    QtCore.SIGNAL('activated(int)'),
                                    self.get_input)
        output = u""
        broken_pipe = False

        try:
            output = self.read(self.buffer_size)
        except OSError:
            broken_pipe = True

        #broken_pipe = True

        if not broken_pipe:
            #my_output = output
            #import codecs
            #f = codecs.open("log.txt", encoding='utf-8', mode='a')
            #f.write( (u"\n\n%s\n\n") % ("#" * 100))
            #for index in xrange(len(my_output)):
            #    f.write(my_output[index])
            #f.close()
            #print "Output: %s" % output

            self.emit(QtCore.SIGNAL("receive"), output)
            self._parent.app.connect(self.notifier,
                                     QtCore.SIGNAL('activated(int)'),
                                     self.get_input)
        else:
            pass
            #print "Broken Pipe"

    def read(self, size=-1, chars=-1, firstline=False):
        """ Decodes data from the stream self.stream and returns the
            resulting object.

            chars indicates the number of characters to read from the
            stream. read() will never return more than chars
            characters, but it might return less, if there are not enough
            characters available.

            size indicates the approximate maximum number of bytes to
            read from the stream for decoding purposes. The decoder
            can modify this setting as appropriate. The default value
            -1 indicates to read and decode as much as possible.  size
            is intended to prevent having to decode huge files in one
            step.

            If firstline is true, and a UnicodeDecodeError happens
            after the first line terminator in the input only the first line
            will be returned, the rest of the input will be kept until the
            next call to read().

            The method should use a greedy read strategy meaning that
            it should read as much data as is allowed within the
            definition of the encoding and the given size, e.g.  if
            optional encoding endings or state markers are available
            on the stream, these should be read too.
        """
        # If we have lines cached, first merge them back into characters
        if self.linebuffer:
            self.charbuffer = u"".join(self.linebuffer)
            self.linebuffer = None

        # read until we get the required number of characters (if available)
        while True:
            # can the request can be satisfied from the character buffer?
            if chars < 0:
                if size < 0:
                    if self.charbuffer:
                        break
                elif len(self.charbuffer) >= size:
                    break
            else:
                if len(self.charbuffer) >= chars:
                    break
            # we need more data
            try:
                if size < 0:
                    newdata = self.stream.read()
                else:
                    newdata = self.stream.read(size)
            except OSError, err:
                if err.errno == EAGAIN:
                    break
                else:
                    raise err

            # decode bytes (those remaining from the last call included)
            data = self.bytebuffer + newdata
            try:
                newchars, decodedbytes = self.decode(data)
            except UnicodeDecodeError, exc:
                if firstline:
                    newchars, decodedbytes = self.decode(data[:exc.start])
                    lines = newchars.splitlines(True)
                    if len(lines)<=1:
                        raise
                else:
                    raise
            # keep undecoded bytes until the next call
            self.bytebuffer = data[decodedbytes:]
            # put new characters in the character buffer
            self.charbuffer += newchars
            # there was no data available
            if not newdata:
                break
        if chars < 0:
            # Return everything we've got
            result = self.charbuffer
            self.charbuffer = u""
        else:
            # Return the first chars characters
            result = self.charbuffer[:chars]
            self.charbuffer = self.charbuffer[chars:]
        return result

    def decode(self, data):
        try:
            chars = data.decode("utf-8")
            return chars, len(data)
        except UnicodeDecodeError, exc:
            return self.decode(data[:exc.start])

    def write(self, text):
        self.stream.write("%s" % str(text))

    def run(self):
        while self.stream.isalive():
            time.sleep(1)

        self.emit(QtCore.SIGNAL("done"))

    def resize(self, rows, cols):
        self.stream.setwinsize(rows, cols)

    def close_pty(self):
        self.stream.terminate(True)
  