class ImportSettings:
    load_bones: bool
    textures_dir_path: str

    def __init__(self, load_bones, textures_path):
        self.load_bones = load_bones
        self.textures_dir_path = textures_path