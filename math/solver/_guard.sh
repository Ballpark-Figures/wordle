# Shared "is one already running?" guard for the sweep wrappers.  Sourced, not run.
#
# The guard used to be `pgrep -x <binary>`, which refused ANY second copy -- so a
# queue of eight runs at different --topk values was rejected outright because an
# unrelated run was still going.  That is too strict: two runs collide only if
# they write the SAME output file.  Different depth, K or answer list means
# different files and no interference beyond sharing the CPU.
#
#   guard_output <binary> <outfile>
#
# Refuses (returns 1) when another process is already writing <outfile>.
# Warns, but allows, when a different run of <binary> is merely competing for CPU.
guard_output() {
    bin="$1"; out="$2"
    same=$(pgrep -f -- "$out" 2>/dev/null | tr '\n' ' ')
    if [ -n "$same" ]; then
        echo "REFUSING: something is already writing $out (pid $same)." >&2
        echo "  Two copies would interleave rows into the same CSV." >&2
        echo "  Change --depth, -k or --answers to get a different output file." >&2
        return 1
    fi
    others=$(pgrep -x "$bin" 2>/dev/null | tr '\n' ' ')
    if [ -n "$others" ]; then
        echo "NOTE: another $bin is running (pid $others). It writes a different file," >&2
        echo "      so this is allowed -- but they share the CPU and both run slower." >&2
    fi
    return 0
}
