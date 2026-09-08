class ImportSettings:
    load_bones: bool
    textures_dir_path: str
    load_animation: bool
    animation_path: str
    load_all_animations: bool
    use_bind_pose_positions: bool
    use_nms: bool
    nms_path: str
    debug_log: bool

    def __init__(self, load_bones, textures_path, load_animation=True,
                 animation_path="", load_all_animations=True,
                 use_bind_pose_positions=True, use_nms=True, nms_path="",
                 debug_log=False):
        self.load_bones = load_bones
        self.textures_dir_path = textures_path
        self.load_animation = load_animation
        self.animation_path = animation_path
        self.load_all_animations = load_all_animations
        self.use_bind_pose_positions = use_bind_pose_positions
        self.use_nms = use_nms
        self.nms_path = nms_path
        self.debug_log = debug_log
