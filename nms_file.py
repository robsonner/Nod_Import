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
    """Use an explicit NMS path or find <model>.nms by priority: 1) .nod folder, 2) Motions/, 3) ../Motions/."""
    if nms_path:
        explicit_path = os.path.abspath(nms_path)
        return explicit_path if os.path.isfile(explicit_path) else None

    model_name = os.path.splitext(os.path.basename(nod_path))[0].lower() + ".nms"
    nod_directory = os.path.dirname(os.path.abspath(nod_path))
    candidate_dirs = [
        nod_directory,
        os.path.join(nod_directory, "Motions"),
        os.path.normpath(os.path.join(nod_directory, "..", "Motions")),
    ]
    for cand_dir in candidate_dirs:
        if not os.path.isdir(cand_dir):
            continue
        try:
            for entry in os.listdir(cand_dir):
                if entry.lower() == model_name:
                    full_path = os.path.join(cand_dir, entry)
                    if os.path.isfile(full_path):
                        return full_path
        except OSError:
            continue
    return None


def resolve_nms_animations(nms_path, animation_directory="", explicit_anim_dir=False):
    """Resolve NMS NAD names case-insensitively across candidate animation directories.

    When ``explicit_anim_dir`` is True and ``animation_directory`` is provided,
    search only in ``animation_directory``.
    Otherwise search in priority order relative to ``animation_directory`` (the .nod folder):
    1) .nod folder, 2) Anims/, 3) ../Anims/.
    """
    motions = load_nms(nms_path)
    nms_dir = os.path.dirname(os.path.abspath(nms_path))
    base_dir = os.path.abspath(animation_directory) if animation_directory else nms_dir

    candidate_dirs = []
    if explicit_anim_dir and animation_directory:
        candidate_dirs.append(base_dir)
    else:
        for d in (
            base_dir,
            os.path.join(base_dir, "Anims"),
            os.path.normpath(os.path.join(base_dir, "..", "Anims")),
        ):
            norm_d = os.path.normcase(os.path.abspath(d))
            if norm_d not in {os.path.normcase(x) for x in candidate_dirs}:
                candidate_dirs.append(os.path.abspath(d))

    directory_files = {}
    scanned_any = False
    for cand_dir in candidate_dirs:
        if not os.path.isdir(cand_dir):
            continue
        try:
            for filename in os.listdir(cand_dir):
                lower_name = filename.lower()
                if lower_name not in directory_files:
                    directory_files[lower_name] = os.path.join(cand_dir, filename)
            scanned_any = True
        except OSError:
            continue

    if not scanned_any:
        print(f"WARNING: cannot scan NAD directory '{animation_directory}'")
        return [], {}

    paths = []
    metadata = {}
    seen = set()
    missing = set()
    for motion in motions:
        resolved_path = directory_files.get(motion.nad_filename.lower())
        if resolved_path is None:
            missing.add(motion.nad_filename)
            continue
        normalized = os.path.normcase(os.path.abspath(resolved_path))
        metadata.setdefault(normalized, []).append(motion)
        if normalized not in seen:
            seen.add(normalized)
            paths.append(resolved_path)

    if missing:
        print(f"WARNING: {len(missing)} NAD files referenced by "
              f"'{nms_path}' were not found in '{animation_directory}'")
    return paths, metadata
