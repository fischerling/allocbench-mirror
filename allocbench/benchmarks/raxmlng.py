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
"""Definition of the RAxML-ng benchmark"""

import os
import re

from allocbench.artifact import GitArtifact
from allocbench.benchmark import Benchmark
from allocbench.util import run_cmd

RUNTIME_RE = re.compile("Elapsed time: (?P<runtime>(\\d*.\\d*)) seconds")

RAXMLNG_VERSION = "0.9.0"


class BenchmarkRaxmlng(Benchmark):
    """RAxML-ng benchmark
    """
    def __init__(self):
        name = "raxmlng"

        super().__init__(name)

        self.cmd = (
            f"raxml-ng --msa {self.build_dir}/data/prim.phy --model GTR+G"
            " --redo --threads 2 --seed 2")

    def prepare(self):
        """Build raxml-ng and download test data if necessary"""
        if os.path.exists(self.build_dir):
            return

        raxmlng_sources = GitArtifact("raxml-ng",
                                      "https://github.com/amkozlov/raxml-ng")
        raxmlng_dir = os.path.join(self.build_dir, "raxml-ng-git")
        raxmlng_builddir = os.path.join(raxmlng_dir, "build")
        self.results["facts"]["versions"]["raxml-ng"] = RAXMLNG_VERSION
        raxmlng_sources.provide(RAXMLNG_VERSION, raxmlng_dir)

        # Create builddir
        os.makedirs(raxmlng_builddir, exist_ok=True)

        # building raxml-ng
        run_cmd(["cmake", ".."], cwd=raxmlng_builddir)
        run_cmd(["make"], cwd=raxmlng_builddir)

        # create symlinks
        for exe in ["raxml-ng"]:
            src = os.path.join(raxmlng_dir, "bin", exe)
            dest = os.path.join(self.build_dir, exe)
            os.link(src, dest)

        raxmlng_data = GitArtifact("raxml-ng-data",
                                   "https://github.com/amkozlov/ng-tutorial")
        raxmlng_data_dir = os.path.join(self.build_dir, "data")
        raxmlng_data.provide("f8f0b6a057a11397b4dad308440746e3436db8b4",
                             raxmlng_data_dir)

    @staticmethod
    def cleanup():
        """Delete data written to the file system"""
        for direntry in os.listdir():
            if direntry.startswith("prim.raxml"):
                os.remove(direntry)

    @staticmethod
    def process_output(result, stdout, stderr, allocator, perm):  # pylint: disable=too-many-arguments, unused-argument, no-self-use
        """extract the runtime from raxmlng's output"""
        result["runtime"] = RUNTIME_RE.search(stdout).group("runtime")

    def summary(self):
        """Create plots showing runtime and VmHWM"""
        import allocbench.plots as plt  # pylint: disable=import-outside-toplevel
        plt.plot(self,
                 "{runtime}",
                 plot_type='bar',
                 fig_options={
                     'ylabel': 'runtime in s',
                     'title': 'raxml-ng tree inference benchmark',
                 },
                 file_postfix="runtime")

        plt.export_stats_to_dataref(self, "runtime")

        plt.plot(self,
                 "{VmHWM}",
                 plot_type='bar',
                 fig_options={
                     'ylabel': 'VmHWM in KB',
                     'title': 'raxml-ng memusage',
                 },
                 file_postfix="memusage")

        plt.export_stats_to_dataref(self, "VmHWM")
