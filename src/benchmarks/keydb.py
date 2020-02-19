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
"""Definition of the keydb, a multi-threaded redis fork benchmark


This benchmark uses the memtier benchmark tool.
"""

import os
import sys
from multiprocessing import cpu_count

from src.artifact import GitArtifact
from src.benchmark import Benchmark
from src.util import print_info, run_cmd


class BenchmarkKeyDB(Benchmark):
    """Definition of the keydb benchmark"""
    def __init__(self):
        name = "keydb"

        self.cmd = "memtier_benchmark –hide-histogram --threads {threads} –data-size {size}"
        self.args = {"threads": Benchmark.scale_threads_for_cpus(1 / 2),
                     "size": [8, 64, 256, 1024, 4096, 16384]}
        
        self.servers = [{
            "name": "keydb",
            "cmd": f"keydb-server --server-threads {cpu_count()//2}",
            "shutdown_cmds": ["{build_dir}/keydb-cli shutdown"]
        }]

        super().__init__(name)

    def prepare(self):
        super().prepare()

        os.makedirs(self.build_dir, exist_ok=True)

        keydb_version = "v5.3.1"
        self.results["facts"]["versions"]["keydb"] = keydb_version
        keydb = GitArtifact("keydb", "https://github.com/JohnSully/KeyDB")

        keydb_dir = os.path.join(self.build_dir, "keydb")
        keydb.provide(keydb_version, keydb_dir)

        # building keyDB
        run_cmd(["make", "-C", keydb_dir, "MALLOC=libc"])

        # create symlinks
        for exe in ["keydb-cli", "keydb-server"]:
            src = os.path.join(keydb_dir, "src", exe)
            dest = os.path.join(self.build_dir, exe)
            if not os.path.exists(dest):
                os.link(src, dest)

        memtier_version = "1.2.17"
        self.results["facts"]["versions"]["memtier"] = memtier_version
        memtier = GitArtifact("memtier", "https://github.com/RedisLabs/memtier_benchmark")

        memtier_dir = os.path.join(self.build_dir, "memtier")
        memtier.provide(memtier_version, memtier_dir)

        # building memtier
        run_cmd(["autoreconf", "-ivf"], cwd=memtier_dir)
        run_cmd(["./configure"], cwd=memtier_dir)
        run_cmd(["make"], cwd=memtier_dir)

        src = os.path.join(memtier_dir, "memtier_benchmark")
        dest = os.path.join(self.build_dir, "memtier_benchmark")
        if not os.path.exists(dest):
            os.link(src, dest)

    @staticmethod
    def process_output(result, stdout, stderr, allocator, perm):
        cmds = ["Sets", "Gets", "Waits", "Totals"]
        stats = ["ops", "hits", "misses", "latency", "throughput"]
        for line in stdout.splitlines():
            line = line.split()
            if line and line[0] in cmds:
                for i, stat in enumerate(stats):
                    result[f"{line[0].lower()}_{stat}"] = line[i + 1]
                    if result[f"{line[0].lower()}_{stat}"] == "---":
                        result[f"{line[0].lower()}_{stat}"] = "nan"
                        
    @staticmethod
    def cleanup():
        if os.path.exists("dump.rdb"):
            os.remove("dump.rdb")

    def summary(self):
        self.plot_fixed_arg("{totals_ops}",
                            ylabel="'OPS/second'",
                            title="'KeyDB Operations: ' + str(perm)",
                            filepostfix="total_ops")

        self.plot_fixed_arg("{keydb_vmhwm}",
                            ylabel="'VmHWM [KB]'",
                            title="'KeyDB Memusage: ' + str(perm)",
                            filepostfix="vmhwm")

keydb = BenchmarkKeyDB()