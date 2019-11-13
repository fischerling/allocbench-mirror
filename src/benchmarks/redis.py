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

"""Definition of the redis benchmark


This benchmark uses the redis benchmark tool included in the redis release
archive. The used parameters are inspired by the ones used in mimalloc-bench."
"""

import os
import re
import subprocess
import sys
from urllib.request import urlretrieve

from src.artifact import ArchiveArtifact
from src.benchmark import Benchmark
from src.util import print_info


REQUESTS_RE = re.compile("(?P<requests>(\\d*.\\d*)) requests per second")


class BenchmarkRedis(Benchmark):
    """Definition of the redis benchmark"""

    def __init__(self):
        name = "redis"

        self.cmd = "redis-benchmark 1000000 -n 1000000 -P 8 -q lpush a 1 2 3 4 5 6 7 8 9 10 lrange a 1 10"
        self.servers = [{"name": "redis",
                         "cmd": "redis-server",
                         "shutdown_cmds": ["{build_dir}/redis-cli shutdown"]}]

        super().__init__(name)

    def prepare(self):
        super().prepare()

        redis_version = "5.0.5"
        self.results["facts"]["versions"]["redis"] = redis_version
        redis = ArchiveArtifact("redis",
                                f"http://download.redis.io/releases/redis-{redis_version}.tar.gz",
                                "tar",
                                "71e38ae09ac70012b5bc326522b976bcb8e269d6")

        redis_dir = os.path.join(self.build_dir, f"redis-{redis_version}")

        redis.provide(self.build_dir)

        # building redis
        proc = subprocess.run(["make", "-C", redis_dir, "MALLOC=libc", "USE_JEMALLOC=no"],
                              # stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

        # create symlinks
        for exe in ["redis-cli", "redis-server", "redis-benchmark"]:
            src = os.path.join(redis_dir, "src", exe)
            dest = os.path.join(self.build_dir, exe)
            if not os.path.exists(dest):
                os.link(src, dest)

    @staticmethod
    def process_output(result, stdout, stderr, allocator, perm):
        result["requests"] = REQUESTS_RE.search(stdout).group("requests")

    @staticmethod
    def cleanup():
        if os.path.exists("dump.rdb"):
            os.remove("dump.rdb")

    def summary(self):
        self.barplot_single_arg("{requests}",
                                ylabel='"requests per s"',
                                title='"redis benchmark"',
                                filepostfix="requests")

        self.export_stats_to_dataref("requests")


redis = BenchmarkRedis()
