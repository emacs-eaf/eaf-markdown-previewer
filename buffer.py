#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2018 Andy Stewart
#
# Author:     Andy Stewart <lazycat.manatee@gmail.com>
# Maintainer: Andy Stewart <lazycat.manatee@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import platform
import subprocess
import tempfile
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from core.utils import PostGui, eval_in_emacs, get_app_dark_mode, get_free_port, interactive, message_to_emacs
from core.webengine import BrowserBuffer
from PyQt6.QtCore import QFileSystemWatcher, QUrl
from retrying import retry


class AppBuffer(BrowserBuffer):

    def __init__(self, buffer_id, url, arguments):
        BrowserBuffer.__init__(self, buffer_id, url, arguments, False)

        self.url = url
        self.preview_file = tempfile.mkstemp(prefix='eaf-', suffix='.html', text=True)[1]
        self.render_js = os.path.join(os.path.dirname(__file__), "render.js")
        self.server_port = get_free_port()
        self.dark_mode = get_app_dark_mode("eaf-markdown-dark-mode")

        self.buffer_widget.init_dark_mode_js(__file__)

        self.draw_progressbar = True

        # Check puml code and Java is installed.
        with open(url, "r", encoding="utf-8", errors="ignore") as f:
            import shutil
            if "```puml" in f.read() and shutil.which("java") is None:
                message_to_emacs("Have PlantUML code in file '{}', you need to install Java to preview normally.".format(os.path.basename(url)))

        self.run_render_server()
        self.render()

        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.fileChanged.connect(self.on_file_changed)
        self.file_watcher.addPath(url)

    def run_render_server(self):
        args = ["node", self.render_js, str(self.server_port)]
        subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)

    @PostGui()
    def on_file_changed(self, *args):
        self.render()

    def retry_if_connection_refused(ex):
        return isinstance(ex, URLError) and isinstance(ex.reason, ConnectionRefusedError)

    @retry(wait_fixed=500, stop_max_attempt_number=10, retry_on_exception=retry_if_connection_refused)
    def render(self):
        params = {
            "input_file": self.url,
            "output_file": self.preview_file,
            "dark_mode": str(self.dark_mode).lower()
        }
        url = 'http://127.0.0.1:{}?{}'.format(self.server_port, urlencode(params))
        with urlopen(url) as f:
            resp = f.read().decode("utf-8")
            if resp == "ok":
                self.buffer_widget.load(QUrl.fromLocalFile(self.preview_file))
                if platform.system() == "Windows":
                    eval_in_emacs('eaf-activate-emacs-window', [])
            else:
                message_to_emacs("preview failed: {}".format(resp))

    @interactive
    def update_theme(self):
        self.dark_mode = get_app_dark_mode("eaf-markdown-dark-mode")
        self.render()
