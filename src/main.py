import sys
from array import array
from pathlib import Path


# RED = "\033[31m"
# # GREEN = "\033[32m"
# BLUE = "\033[34m"
# RESET = "\033[0m"

def read_lines(path):
    """Read raw bytes and split on LF, preserving CR characters."""
    data = Path(path).read_bytes()

    if data == b"":
        return []

    lines = data.split(b"\n")

    # A final newline does not create an extra line.
    if lines[-1] == b"":
        lines.pop()

    return lines


def myers_diff(a, b):
    """
    Return a minimal edit script:
    EQUAL, DELETE, INSERT.

    Works with any sequences, including bytes lines and
    Unicode characters.

    The trace is kept as a list of packed integer arrays instead of
    dicts, so memory stays proportional to the number of diagonals
    visited rather than being inflated by per-entry dictionary
    overhead.
    """
    n, m = len(a), len(b)

    if n == 0:
        return [("INSERT", value) for value in b]

    if m == 0:
        return [("DELETE", value) for value in a]

    offset = n + m

    # v[k] is the furthest x reached on diagonal k, stored at
    # v[k + offset].
    v = [0] * (2 * offset + 3)
    v[offset + 1] = 0

    # trace[d] holds the v values for k in [-(d - 1), d - 1] before
    # iteration d, indexed by (k + d - 1) // 2.
    trace = [array("i", [0])]

    for d in range(n + m + 1):
        if d:
            trace.append(
                array("i", v[offset - d + 1 : offset + d : 2])
            )

        for k in range(-d, d + 1, 2):
            index = k + offset

            if (
                k == -d
                or (
                    k != d
                    and v[index - 1] < v[index + 1]
                )
            ):
                x = v[index + 1]
            else:
                x = v[index - 1] + 1

            y = x - k

            # Follow the diagonal while elements match.
            while x < n and y < m and a[x] == b[y]:
                x += 1
                y += 1

            v[index] = x

            if x >= n and y >= m:
                return backtrack(trace, a, b)

    return []


def backtrack(trace, a, b):
    """Reconstruct the edit script from Myers' trace."""
    x, y = len(a), len(b)
    result = []

    for d in range(len(trace) - 1, -1, -1):
        row = trace[d]
        k = x - y

        if (
            k == -d
            or (
                k != d
                and row[(k + d - 2) // 2] < row[(k + d) // 2]
            )
        ):
            previous_k = k + 1
        else:
            previous_k = k - 1

        previous_x = row[(previous_k + d - 1) // 2]
        previous_y = previous_x - previous_k

        while x > previous_x and y > previous_y:
            result.append(("EQUAL", a[x - 1]))
            x -= 1
            y -= 1

        if d == 0:
            break

        if x == previous_x:
            result.append(("INSERT", b[y - 1]))
            y -= 1
        else:
            result.append(("DELETE", a[x - 1]))
            x -= 1

    while x > 0 and y > 0:
        result.append(("EQUAL", a[x - 1]))
        x -= 1
        y -= 1

    while x > 0:
        result.append(("DELETE", a[x - 1]))
        x -= 1

    while y > 0:
        result.append(("INSERT", b[y - 1]))
        y -= 1

    result.reverse()
    return result


def changed_ranges(old, new):
    """
    Return the changed Unicode character ranges in both strings.
    Each range is half-open: start-end.
    """
    operations = myers_diff(list(old), list(new))
    old_positions = []
    new_positions = []
    old_pos = 0
    new_pos = 0

    for kind, char in operations:
        if kind == "EQUAL":
            old_pos += 1
            new_pos += 1
        elif kind == "DELETE":
            old_positions.append(old_pos)
            old_pos += 1
        elif kind == "INSERT":
            new_positions.append(new_pos)
            new_pos += 1

    def to_ranges(positions):
        if not positions:
            return "."

        ranges = []
        start = previous = positions[0]

        for position in positions[1:]:
            if position == previous + 1:
                previous = position
            else:
                ranges.append(f"{start}-{previous + 1}")
                start = previous = position

        ranges.append(f"{start}-{previous + 1}")
        return ",".join(ranges)

    return to_ranges(old_positions), to_ranges(new_positions)


def write_line(prefix, line):
    """Write a prefix and the exact original line bytes."""
    sys.stdout.buffer.write(prefix + line + b"\n")


def run_diff(old_lines, new_lines, highlight=False):
    operations = myers_diff(old_lines, new_lines)
    i = 0

    while i < len(operations):
        kind, line = operations[i]

        if kind == "EQUAL":
            write_line(b" ", line)
            i += 1
            continue

        # Gather a complete change block.
        deleted = []
        inserted = []

        while i < len(operations) and operations[i][0] != "EQUAL":
            op, value = operations[i]

            if op == "DELETE":
                deleted.append(value)
            else:
                inserted.append(value)

            i += 1

        # Assignment requires all deletions before insertions.
        # Print all deletions first.
        for line in deleted:
            write_line(b"-", line)

        # Then print insertions.
        # If an insertion has a matching deletion, immediately
        # print its character-highlight line.
        for index, line in enumerate(inserted):
            write_line(b"+", line)

            if highlight and index < len(deleted):
                old_line = deleted[index]

                old_text = old_line.decode("utf-8")
                new_text = line.decode("utf-8")

                old_ranges, new_ranges = changed_ranges(
                    old_text, new_text
                )

                report = f"? {old_ranges} | {new_ranges}\n"
                sys.stdout.buffer.write(report.encode("utf-8"))


def main():
    if len(sys.argv) != 4:
        print(
            "Usage: python main.py lines A B\n"
            "   or: python main.py highlight A B",
            file=sys.stderr,
        )
        return 2

    command, file_a, file_b = sys.argv[1:]

    if command not in ("lines", "highlight"):
        print(f"Unknown command: {command}", file=sys.stderr)
        return 2

    try:
        a = read_lines(file_a)
        b = read_lines(file_b)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    try:
        run_diff(a, b, highlight=(command == "highlight"))
    except UnicodeDecodeError as error:
        print(f"Error decoding UTF-8: {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
