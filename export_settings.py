class ExportSettings:
    export_bones: bool
    preserve_imported_bind_pose: bool
    selected_only: bool
    model_version: int
    debug_log: bool

    def __init__(
        self,
        export_bones: bool = True,
        preserve_imported_bind_pose: bool = True,
        selected_only: bool = False,
        model_version: int = 7,
        debug_log: bool = False,
    ):
        self.export_bones = export_bones
        self.preserve_imported_bind_pose = preserve_imported_bind_pose
        self.selected_only = selected_only
        self.model_version = model_version
        self.debug_log = debug_log
