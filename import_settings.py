class ImportSettings:
    load_bones: bool
    textures_dir_path: str
    load_animation: bool
    animation_path: str

    def __init__(self, load_bones, textures_path, load_animation=True,
                 animation_path=""):
        self.load_bones = load_bones
        self.textures_dir_path = textures_path
        self.load_animation = load_animation
        self.animation_path = animation_path
