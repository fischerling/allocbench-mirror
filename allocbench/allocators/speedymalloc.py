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
"""Speedymalloc

Speedymalloc is a cached bump pointer allocator.
A bump pointer allocator makes the biggest possible tradeoff between speed and
memory in speeds favor. Memory is mmapped per thread and never freed.
"""

from allocbench.artifact import GitArtifact
from allocbench.allocator import Allocator

VERSION = "65312883f5e0a35b66b45824d581d72338ac5a05"


class Speedymalloc(Allocator):
    """Speedymalloc definition for allocbench"""

    sources = GitArtifact("speedymalloc",
                          "https://gitlab.cs.fau.de/flow/speedymalloc.git")

    def __init__(self, name, **kwargs):

        configuration = "--buildtype=release "
        for option, value in kwargs.get("options", {}).items():
            configuration += f"-D{option}={value} "

        self.build_cmds = [
            f"meson {{srcdir}} {{dir}} {configuration}", "ninja -C {dir}"
        ]

        self.ld_preload = "{dir}/src/libspeedymalloc.so"
        super().__init__(name, **kwargs)


# pylint: disable=invalid-name
speedymalloc = Speedymalloc("speedymalloc", version=VERSION)

speedymalloc_core_local_rseq = Speedymalloc(
    "speedymalloc_core_local_rseq",
    options={"lab_type": "core-local-rseq"},
    version=VERSION)

speedymalloc_core_local_treiber_stack = Speedymalloc(
    "speedymalloc_core_local_rseq",
    options={"lab_type": "core-local-treiber-stack"},
    version=VERSION)
speedymalloc_no_lab = Speedymalloc("speedymalloc_only_glab",
                                   options={"lab_type": 'none'},
                                   version=VERSION)

speedymalloc_no_madv_free = Speedymalloc("speedymalloc_no_madv_free",
                                         options={"madvise_free": "false"},
                                         version=VERSION)

speedymalloc_no_madv_willneed = Speedymalloc(
    "speedymalloc_no_madv_willneed",
    options={"madvise_willneed": "false"},
    version=VERSION)

speedymalloc_4095_sc_32 = Speedymalloc("speedymalloc_4095_sc_32",
                                       options={
                                           "cache_bins": 4095,
                                           "cache_bin_separation": 32
                                       },
                                       version=VERSION)

speedymalloc_4095_sc_128 = Speedymalloc("speedymalloc_4095_sc_128",
                                        options={
                                            "cache_bins": 4095,
                                            "cache_bin_separation": 128
                                        },
                                        version=VERSION)

speedymalloc_no_glab = Speedymalloc("speedymalloc_no_glab",
                                    options={"max_lab_size": -1},
                                    version=VERSION)
