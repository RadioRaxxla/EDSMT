"""How many files of a kind a folder holds and how big they are (1.10042).

Settings > Your data uses it for the saved map pictures. Plain file work."""
import os


def count_and_size(folder, kinds):
    """(count, bytes) of the files in `folder` whose names end in `kinds`."""
    count = size = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0
    for name in names:
        full = os.path.join(folder, name)
        if name.lower().endswith(tuple(kinds)) and os.path.isfile(full):
            try:
                size += os.path.getsize(full)
            except OSError:
                continue
            count += 1
    return count, size


def size_words(size):
    """A size a player reads: 0 KB, 1.5 KB, 5.0 MB, 1.2 GB."""
    size = max(0, int(size or 0))
    if size >= 1024 ** 3:
        return "%.1f GB" % (size / 1024 ** 3)
    if size >= 1024 ** 2:
        return "%.1f MB" % (size / 1024 ** 2)
    if size == 0 or size % 1024 == 0 and size < 1024 ** 2:
        return "%d KB" % (size // 1024)
    return "%.1f KB" % (size / 1024)


def pictures_line(count, size):
    if not count:
        return "No saved map pictures yet"
    return "%d saved map picture%s, %s" % (count, "" if count == 1 else "s", size_words(size))
