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
"""Definition of the falsesharing benchmark"""

import re

from allocbench.benchmark import Benchmark

TIME_RE = re.compile("^Time elapsed = (?P<time>\\d*\\.\\d*) seconds.$")


class BenchmarkFalsesharing(Benchmark):
    """Falsesharing benchmark.

    This benchmarks makes small allocations and writes to them multiple
    times. If the allocated objects are on the same cache line the writes
    will be expensive because of cache thrashing.
    """
    def __init__(self):
        name = "falsesharing"

        self.cmd = "cache-{bench}{binary_suffix} {threads} 100 8 10000000"

        self.args = {
            "bench": ["thrash", "scratch"],
            "threads": Benchmark.scale_threads_for_cpus(1)
        }

        self.requirements = ["cache-thrash", "cache-scratch"]
        super().__init__(name)

    @staticmethod
    def process_output(result, stdout, stderr, allocator, perm):  # pylint: disable=too-many-arguments, unused-argument
        """Extract and store the needed time from stdout"""
        result["time"] = TIME_RE.match(stdout).group("time")

    def summary(self):
        """Create plots showing the speedup and L1 data cache miss rate"""
        import allocbench.plots as plt  # pylint: disable=import-outside-toplevel
        args = self.results["args"]
        allocators = self.results["allocators"]

        # calculate relevant datapoints: speedup, l1-cache-misses
        for bench in self.results["args"]["bench"]:
            for allocator in allocators:

                sequential_perm = self.Perm(bench=bench, threads=1)
                for perm in self.iterate_args(fixed={"bench": bench},
                                              args=args):
                    for i, measure in enumerate(self.results[allocator][perm]):
                        sequential_time = float(self.results[allocator]
                                                [sequential_perm][i]["time"])
                        measure["speedup"] = sequential_time / float(
                            measure["time"])
                        measure["l1chache_misses"] = (
                            float(measure['L1-dcache-load-misses']) /
                            float(measure['L1-dcache-loads'])) * 100

        # delete and recalculate stats
        del self.results["stats"]
        self.calc_desc_statistics()

        plt.plot(self,
                 "{speedup}",
                 x_args=["bench"],
                 fig_options={
                     'ylabel': "Speedup",
                     'title': "Speedup: {fixed_part_str}",
                     'autoticks': False,
                 },
                 file_postfix="speedup")

        plt.plot(self,
                 "{l1chache_misses}",
                 x_args=["bench"],
                 fig_options={
                     'ylabel': "l1 cache misses in %",
                     'title': "cache misses: {fixed_part_str}",
                     'autoticks': False,
                 },
                 file_postfix="l1-misses")

        plt.write_tex_table(self, [{
            "label": "Speedup",
            "expression": "{speedup}",
            "sort": ">"
        }],
                            file_postfix="speedup.table")

        # plt.export_stats_to_csv(self, "speedup", "time")
        # plt.export_stats_to_csv(self, "l1chache_misses", "l1-misses")

        # pgfplots
        for bench in args["bench"]:
            plt.pgfplot(self,
                        self.iterate_args(fixed={"bench": bench}, args=args),
                        "int(perm.threads)",
                        "{speedup}",
                        xlabel="Threads",
                        ylabel="Speedup",
                        title=f"{bench}: Speedup",
                        postfix=f"{bench}.speedup")

        # create pgfplot legend
        plt.pgfplot_legend(self)
