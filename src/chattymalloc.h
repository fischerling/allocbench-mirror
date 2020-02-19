/*
Copyright 2018-2020 Florian Fischer <florian.fl.fischer@fau.de>

This file is part of allocbench.

allocbench is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

allocbench is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with allocbench.  If not, see <http://www.gnu.org/licenses/>.
*/

#include <sys/types.h>

enum functions{MALLOC, FREE, REALLOC, CALLOC, MEMALIGN, POSIX_MEMALIGN, VALLOC, PVALLOC, ALIGNED_ALLOC};

typedef struct trace {
  pid_t tid;
  void* ptr;
  size_t size;
  size_t var_arg;
  char func;
} __attribute__((packed)) trace_t;
