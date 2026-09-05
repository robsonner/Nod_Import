import os


class NmsMotion:
    def __init__(self, mode, nad_filename, flags, line_number):
        self.mode = mode
        self.nad_filename = nad_filename
        self.flags = tuple(flags)
        self.line_number = line_number


def load_nms(filepath):
    """Read motion-to-NAD mappings from an ASCII NMS file."""
    motions = []
    with open(filepath, "r", encoding="cp1252", errors="replace") as stream:
        for line_number, source_line in enumerate(stream, 1):
            line = source_line.split(";", 1)[0].strip()
            if not line:
                continue
            fields = line.split()
            keyword = fields[0].lower()
            if keyword in {"tag", "mouth"}:
                continue
            if len(fields) < 2 or not fields[1].lower().endswith(".nad"):
                print(f"WARNING: ignoring malformed NMS line {line_number}: "
                      f"{source_line.rstrip()}")
                continue
            motions.append(NmsMotion(fields[0], fields[1], fields[2:],
                                     line_number))
    return motions


def find_nms_for_nod(nod_path, nms_path=""):
    """Use an explicit NMS path or find <model>.nms beside the NOD file."""
    if nms_path:
        explicit_path = os.path.abspath(nms_path)
        return explicit_path if os.path.isfile(explicit_path) else None

    model_name = os.path.splitext(os.path.basename(nod_path))[0] + ".nms"
    nod_directory = os.path.dirname(os.path.abspath(nod_path))
    automatic_path = os.path.join(nod_directory, model_name)
    return automatic_path if os.path.isfile(automatic_path) else None


def resolve_nms_animations(nms_path, animation_directory):
    """Resolve NMS NAD names case-insensitively and retain their metadata."""
    motions = load_nms(nms_path)
    try:
        directory_files = {
            filename.lower(): filename
            for filename in os.listdir(animation_directory)
        }
    except OSError as error:
        print(f"WARNING: cannot scan NAD directory "
              f"'{animation_directory}': {error}")
        return [], {}

    paths = []
    metadata = {}
    seen = set()
    missing = set()
    for motion in motions:
        actual_name = directory_files.get(motion.nad_filename.lower())
        if actual_name is None:
            missing.add(motion.nad_filename)
            continue
        path = os.path.join(animation_directory, actual_name)
        normalized = os.path.normcase(os.path.abspath(path))
        metadata.setdefault(normalized, []).append(motion)
        if normalized not in seen:
            seen.add(normalized)
            paths.append(path)

    if missing:
        print(f"WARNING: {len(missing)} NAD files referenced by "
              f"'{nms_path}' were not found in '{animation_directory}'")
    return paths, metadata
