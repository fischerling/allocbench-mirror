import inspect
import os


"""Dict holding facts about the current benchmark run"""
facts = {}

"""Verbosity level -1: quiet, 0: status, 1: info, 2: stdout of subcommands, 3: debug info"""
verbosity = 0

"""Dict holding the allocators to compare"""
allocators = {}

"""File were the allocators definitions are loaded from"""
allocators_file = None

"""Root directory of allocbench"""
allocbenchdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
allocbenchdir = os.path.dirname(allocbenchdir)

"""Path of the build directory"""
builddir = os.path.join(allocbenchdir, "build")

"""Directory were the benchmark results are stored"""
resdir = None

"""Source directory for all benchmarks"""
benchsrcdir = os.path.join(allocbenchdir, "src", "benchmarks")

"""List of available benchmarks"""
benchmarks = [e[:-3] for e in os.listdir(os.path.join(allocbenchdir, benchsrcdir))
              if e[-3:] == ".py" and e != "__init__.py"]
