.PHONY: all clean bench

.DEFAULT_GOAL = all

SRCDIR=src
BENCHSRCDIR=$(SRCDIR)/benchmarks
BENCH_C_SOURCES = $(shell find $(BENCHSRCDIR) -name "*.c")
BENCH_CC_SOURCES = $(shell find $(BENCHSRCDIR) -name "*.cc")

OBJDIR = ./build

CC = gcc
CXX = g++

WARNFLAGS = -Wall -Wextra
COMMONFLAGS = -fno-builtin -fPIC -DPIC -pthread
OPTFLAGS = -O3 -DNDEBUG
# OPTFLAGS = -O0 -g3

CXXFLAGS = -std=c++11 -I. $(OPTFLAGS) $(WARNFLAGS) $(COMMONFLAGS) -fno-exceptions
CFLAGS = -I. $(OPTFLAGS) $(WARNFLAGS) $(COMMONFLAGS)

LDFLAGS = -pthread -static-libgcc
LDXXFLAGS = $(LDFLAGS) -static-libstdc++

VPATH = $(sort $(dir $(BENCH_C_SOURCES) $(BENCH_CC_SOURCES)))

GLIBC_NOTC = $(PWD)/../glibc/glibc-install-notc/lib

BENCH_OBJECTS = $(notdir $(BENCH_CC_SOURCES:.cc=.o)) $(notdir $(BENCH_C_SOURCES:.c=.o))
BENCH_OBJPRE = $(addprefix $(OBJDIR)/,$(BENCH_OBJECTS))
MAKEFILE_LIST = Makefile

BENCH_TARGETS = $(BENCH_OBJPRE:.o=) $(OBJDIR)/trace_run

NOTC_TARGETS = $(BENCH_TARGETS:=-glibc-notc)

all: $(BENCH_TARGETS) $(NOTC_TARGETS) $(OBJDIR)/chattymalloc.so $(OBJDIR)/print_status_on_exit.so $(OBJDIR)/ccinfo

$(OBJDIR)/ccinfo:
	$(CC) -v 2> $@

$(OBJDIR)/print_status_on_exit.so: $(SRCDIR)/print_status_on_exit.c $(MAKEFILE_LIST)
	$(CC) -shared $(CFLAGS) -o $@ $< -ldl

$(OBJDIR)/chattymalloc.so: $(SRCDIR)/chattymalloc.c $(MAKEFILE_LIST)
	$(CC) -shared $(CFLAGS) -o $@ $< -ldl

$(OBJDIR)/trace_run: $(SRCDIR)/trace_run.c $(MAKEFILE_LIST)
	$(CC) $(LDFALGS) $(CFLAGS) -o $@ $<

$(OBJDIR)/trace_run-glibc-notc: $(OBJDIR)/trace_run $(MAKEFILE_LIST)
	cp $< $@
	patchelf --set-interpreter $(GLIBC_NOTC)/ld-linux-x86-64.so.2 $@
	patchelf --set-rpath $(GLIBC_NOTC) $@

$(OBJDIR)/larson: $(OBJDIR)/larson.o
	$(CXX) $(LDXXFLAGS) -o $@ $^

$(OBJDIR)/larson-glibc-notc: $(OBJDIR)/larson
	cp $< $@
	patchelf --set-interpreter $(GLIBC_NOTC)/ld-linux-x86-64.so.2 $@
	patchelf --set-rpath $(GLIBC_NOTC) $@

$(OBJDIR)/cache-thrash: $(OBJDIR)/cache-thrash.o
	$(CXX) $(LDXXFLAGS) -o $@ $^

$(OBJDIR)/cache-thrash-glibc-notc: $(OBJDIR)/cache-thrash
	cp $< $@
	patchelf --set-interpreter $(GLIBC_NOTC)/ld-linux-x86-64.so.2 $@
	patchelf --set-rpath $(GLIBC_NOTC) $@

$(OBJDIR)/cache-scratch: $(OBJDIR)/cache-scratch.o
	$(CXX) $(LDXXFLAGS) -o $@ $^

$(OBJDIR)/cache-scratch-glibc-notc: $(OBJDIR)/cache-scratch
	cp $< $@
	patchelf --set-interpreter $(GLIBC_NOTC)/ld-linux-x86-64.so.2 $@
	patchelf --set-rpath $(GLIBC_NOTC) $@

$(OBJDIR)/bench_loop: $(OBJDIR)/bench_loop.o
	$(CC) $(LDFLAGS) -o $@ $^

$(OBJDIR)/bench_loop-glibc-notc: $(OBJDIR)/bench_loop
	cp $< $@
	patchelf --set-interpreter $(GLIBC_NOTC)/ld-linux-x86-64.so.2 $@
	patchelf --set-rpath $(GLIBC_NOTC) $@

$(OBJDIR)/%.o : %.c $(OBJDIR) $(MAKEFILE_LIST)
	$(CC) -c $(CFLAGS) -o $@ $<

$(OBJDIR)/%.o : %.cc $(OBJDIR) $(MAKEFILE_LIST)
	$(CXX) -c $(CXXFLAGS) -o $@ $<

$(OBJDIR):
	mkdir -p $@

clean:
	rm -rf $(OBJDIR)
	rm -rf $(DEPDIR)

