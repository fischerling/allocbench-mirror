# Copyright 2018-2020 Florian Fischer <florian.fl.fischer@fau.de>
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

from allocbench.artifact import ArchiveArtifact, GitArtifact
from allocbench.benchmark import Benchmark
import allocbench.plots as plt


class BenchmarkFd(Benchmark):
    """fd benchmark
    """
    def __init__(self):
        name = "fd"
        self.cmd = "fd -HI -e c '.*[0-9].*' {linux_files}"
        super().__init__(name)

        linux = GitArtifact(
            "linux",
            "git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git")
        linux_version = "v5.3"
        self.linux_files = linux.provide(linux_version)

        if os.path.exists(self.build_dir):
            return

        fd_version = "v7.4.0"
        self.results["facts"]["versions"]["fd"] = fd_version
        fd_url = ("https://github.com/sharkdp/fd/releases/latest/download/"
                  f"fd-{fd_version}-x86_64-unknown-linux-gnu.tar.gz")

        fd_artifact = ArchiveArtifact(
            "fd", fd_url, "tar", "a5d8e7c8484449aa324a46abfdfaf026d7de77ee")

        fd_dir = os.path.join(self.build_dir, "fd_sources")
        fd_artifact.provide(fd_dir)

        # create symlinks
        for exe in ["fd"]:
            src = os.path.join(fd_dir,
                               f"fd-{fd_version}-x86_64-unknown-linux-gnu",
                               exe)
            dest = os.path.join(self.build_dir, exe)
            os.link(src, dest)

    def summary(self):
        plt.plot(self,
                 "{task-clock}",
                 plot_type='bar',
                 fig_options={
                     'ylabel': "runtime in ms",
                     'title': "fd runtime",
                 },
                 file_postfix="runtime")

        plt.export_stats_to_dataref(self, "task-clock")

        plt.plot(self,
                 "{VmHWM}",
                 plot_type='bar',
                 fig_options={
                     'ylabel': "VmHWM in KB",
                     'title': "fd memusage"
                 },
                 file_postfix="memusage")

        plt.export_stats_to_dataref(self, "VmHWM")
