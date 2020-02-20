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
"""Definition of the loop micro benchmark

This benchmark allocates and immediately deallocates a pseudo random sized allocation
N times in T threads. The acquired memory is neither read nor written. Not using the
allocations at all maybe seems odd but this micro benchmark should only measure
the allocators fast paths, scalability and management overhead.
Using the allocations will add cache effects to our results which are
measured for example in the false sharing or larson benchmarks.

Observations:
* Glibc's factor two faster for allocations <= 1024B
* TCMalloc suffers when allocating only small chunks

Interpretation:
* A significant higher cache miss rate than other allocators could mean that
  internals suffer from false sharing (TCMalloc).
* Speed changes with constant threads but changing sizes may show performance
  differences in differing strategies for seperate sizes (glibc thread caches < 1032B)
"""

from src.benchmark import Benchmark
import src.plots as plt


class BenchmarkLoop(Benchmark):
    """Loop micro benchmark

    This benchmark allocates and frees n blocks in t concurrent threads.
    """
    def __init__(self):
        name = "loop"

        self.cmd = "loop{binary_suffix} {nthreads} 1000000 {maxsize}"

        self.args = {
            "maxsize": [2**x for x in range(6, 16)],
            "nthreads": Benchmark.scale_threads_for_cpus(2)
        }

        self.requirements = ["loop"]
        super().__init__(name)

    def summary(self):
        # Speed
        plt.plot_fixed_arg(self,
                           "perm.nthreads / ({task-clock}/1000)",
                           ylabel="MOPS/cpu-second",
                           title="Loop: {arg} {arg_value}",
                           filepostfix="time",
                           autoticks=False)

        # L1 cache misses
        plt.plot_fixed_arg(
            self,
            "({L1-dcache-load-misses}/{L1-dcache-loads})*100",
            ylabel="L1 misses in %",
            title="Loop l1 cache misses: {arg} {arg_value}",
            filepostfix="l1misses",
            autoticks=False)

        # Speed Matrix
        plt.write_best_doublearg_tex_table(
            self,
            "perm.nthreads / ({task-clock}/1000)",
            filepostfix="time.matrix")

        plt.write_tex_table(self, [{
            "label": "MOPS/s",
            "expression": "perm.nthreads / ({task-clock}/1000)",
            "sort": ">"
        }],
                            filepostfix="mops.table")

        plt.export_stats_to_csv(self, "task-clock")
        plt.export_stats_to_dataref(self, "task-clock")

        # pgfplot test
        plt.pgfplot_linear(self,
                           self.iterate_args_fixed({"maxsize": 1024},
                                                   args=self.results["args"]),
                           "int(perm.nthreads)",
                           "perm.nthreads / ({task-clock}/1000)",
                           xlabel="Threads",
                           ylabel="MOPS/cpu-second",
                           title="Loop: 1024B",
                           postfix='mops_1024B')

        # create pgfplot legend
        plt.pgfplot_legend(self)


loop = BenchmarkLoop()
