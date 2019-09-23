# Copyright 2018-2019 Florian Fischer <florian.fl.fischer@fau.de>
#
# This file is part of allocbench.
#
# allocbench is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# allocbench is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with allocbench.  If not, see <http://www.gnu.org/licenses/>.

"""Definition of the fd benchmark"""

import os
import re
import subprocess
import sys
from urllib.request import urlretrieve

from src.artifact import ArchiveArtifact, GitArtifact
from src.benchmark import Benchmark
from src.util import print_info


class BenchmarkFd(Benchmark):
    """fd benchmark
    """

    def __init__(self):
        name = "fd"
        super().__init__(name)
        
        self.cmd = "fd -HI -e c '.*[0-9].*' {build_dir}/linux"

    def prepare(self):
        super().prepare()

        fd_version = "v7.4.0"
        self.results["facts"]["versions"]["fd"] = fd_version
        fd_url = ("https://github.com/sharkdp/fd/releases/latest/download/"
                  f"fd-{fd_version}-x86_64-unknown-linux-gnu.tar.gz")

        fd = ArchiveArtifact("fd", fd_url, "tar", "a5d8e7c8484449aa324a46abfdfaf026d7de77ee")

        fd_dir = os.path.join(self.build_dir, "fd_sources")
        fd.provide(fd_dir)

        # create symlinks
        for exe in ["fd"]:
            src = os.path.join(fd_dir, f"fd-{fd_version}-x86_64-unknown-linux-gnu", exe)
            dest = os.path.join(self.build_dir, exe)
            os.link(src, dest)
        

        linux = GitArtifact("linux", "git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git")
        linux_version = "v5.3"
        linux.provide(linux_version, os.path.join(self.build_dir, "linux"))

    def summary(self):
        self.barplot_single_arg("{task-clock}",
                                ylabel='"runtime in s"',
                                title='"fd runtime"',
                                filepostfix="runtime")

        self.export_stats_to_dataref("task-clock")

        self.barplot_single_arg("{VmHWM}",
                                ylabel='"VmHWM in KB"',
                                title='"fd memusage"',
                                filepostfix="memusage")

        self.export_stats_to_dataref("VmHWM")


fd = BenchmarkFd()
