class ImportSettings:
    load_bones: bool
    textures_dir_path: str
    load_animation: bool
    animation_path: str
    use_nms: bool
    nms_path: str
    nms_anims_dir: str
    debug_log: bool
    nod_path: str

    def __init__(self, load_bones, textures_path="", load_animation=True,
                 animation_path="", use_nms=True, nms_path="",
                 nms_anims_dir="", debug_log=False, nod_path=""):
        self.load_bones = load_bones
        self.textures_dir_path = textures_path
        self.textures_path = textures_path
        self.load_animation = load_animation
        self.animation_path = animation_path
        self.use_nms = use_nms
        self.nms_path = nms_path
        self.nms_anims_dir = nms_anims_dir
        self.debug_log = debug_log
        self.nod_path = nod_path
