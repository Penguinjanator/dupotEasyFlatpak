class PermissionOverrideEntity:

    FIELD_LABEL = "label"
    FIELD_TYPE = "type"
    FIELD_VALUE = "value"
    FIELD_SUB_VALUE_YES = "subValueYes"
    FIELD_SUB_VALUE_NO = "subValueNo"
    FIELD_DEFAULT = "default"

    TYPE_FILESYSTEM = "filesystem"
    TYPE_FILESYSTEM_NO_PROMPT = "filesystem_noprompt"
    TYPE_INSTALL_YES_NO = "install_flatpak_yesno"
    TYPE_INSTALL_FORGE_YES_NO = "install_forge_flatpak_yesno"
    TYPE_SOUND = "sound"
    TYPE_SOCKET = "socket"
    TYPE_DEVICE = "device"
    TYPE_SHARE = "share"
    TYPE_ENV_YES_NO = "env_yesno"

    DEFAULT_SOUND_SOCKET = "pulseaudio"

    # Toggle types: switch granting/revoking one value of a [Context] key of
    # the flatpak metadata — type -> (metadata key, grant flag, revoke flag)
    TOGGLE_TYPE_LIST = {
        TYPE_SOUND: ("sockets", "--socket", "--nosocket"),
        TYPE_SOCKET: ("sockets", "--socket", "--nosocket"),
        TYPE_DEVICE: ("devices", "--device", "--nodevice"),
        TYPE_SHARE: ("shared", "--share", "--unshare"),
    }

    _label: str = ""
    _type: str = ""
    _value: str = ""
    _sub_value_yes: str = "1"
    _sub_value_no: str = "0"
    _default: bool = True

    def __init__(self, raw_obj: object):

        if self.FIELD_LABEL in raw_obj:
            self._label = raw_obj[self.FIELD_LABEL]
        if self.FIELD_TYPE in raw_obj:
            self._type = raw_obj[self.FIELD_TYPE]
        if self.FIELD_VALUE in raw_obj:
            self._value = raw_obj[self.FIELD_VALUE]
        if self.FIELD_SUB_VALUE_YES in raw_obj:
            self._sub_value_yes = str(raw_obj[self.FIELD_SUB_VALUE_YES])
        if self.FIELD_SUB_VALUE_NO in raw_obj:
            self._sub_value_no = str(raw_obj[self.FIELD_SUB_VALUE_NO])
        if self.FIELD_DEFAULT in raw_obj:
            self._default = bool(raw_obj[self.FIELD_DEFAULT])

        pass

    def is_filesystem(self) -> bool:
        return self._type == self.TYPE_FILESYSTEM

    GAME_PATH_LABEL = "recipe_indicate_your_game_path_label"

    def is_game_path(self) -> bool:
        """Filesystem prompt for the games directory — the only one prefilled
        with the "game path" user setting (not recording/projects paths)."""
        return self.is_filesystem() and self._label == self.GAME_PATH_LABEL

    def is_filesystem_no_prompt(self) -> bool:
        return self._type == self.TYPE_FILESYSTEM_NO_PROMPT

    def is_sound(self) -> bool:
        return self._type == self.TYPE_SOUND

    def is_toggle(self) -> bool:
        """Socket / device / share switch (sound included)."""
        return self._type in self.TOGGLE_TYPE_LIST

    def get_toggle_metadata_key(self) -> str:
        return self.TOGGLE_TYPE_LIST[self._type][0]

    def get_toggle_flag(self, enable: bool) -> str:
        grant_flag, revoke_flag = self.TOGGLE_TYPE_LIST[self._type][1:]
        return f"{grant_flag if enable else revoke_flag}={self.get_value()}"

    def is_env_yes_no(self) -> bool:
        return self._type == self.TYPE_ENV_YES_NO

    def get_env_flag(self, enable: bool) -> str:
        return f"--env={self._value}={self.get_sub_value(enable)}"

    def is_install_flatpak_yes_no(self) -> bool:
        return self._type == self.TYPE_INSTALL_YES_NO

    def is_install_forge_flatpak_yes_no(self) -> bool:
        return self._type == self.TYPE_INSTALL_FORGE_YES_NO

    def is_install_yes_no(self) -> bool:
        """Any "also install this other flatpak" switch (Flathub or forge)."""
        return self.is_install_flatpak_yes_no() or self.is_install_forge_flatpak_yes_no()

    def get_label(self) -> str:
        return self._label

    def get_value(self) -> str:
        if self.is_sound() and not self._value:
            return self.DEFAULT_SOUND_SOCKET
        return self._value

    def get_sub_value(self, enable: bool) -> str:
        return self._sub_value_yes if enable else self._sub_value_no

    def is_active_by_default(self) -> bool:
        """Initial state of the switch on install (optional "default": false)."""
        return self._default


# {
#    "label": "recipe_share_your_home_label",
#    "type": "filesystem_noprompt",
#    "value": "home",
# }
# {
#    "label": "recipe_allow_sound_label",
#    "type": "sound",
#    "value": "pulseaudio",   (optional, socket granted via --socket=)
# }
# {
#    "label": "recipe_allow_wayland_label",
#    "type": "socket",        (also "device": all/input/kvm/shm, "share": network/ipc)
#    "value": "wayland",
# }
# {
#    "label": "recipe_enable_mangohud",
#    "type": "env_yesno",
#    "value": "MANGOHUD",
#    "subValueYes": "1",      (optional, default "1")
#    "subValueNo": "0",       (optional, default "0")
# }
# {
#    "label": "recipe_should_installMangoHud",
#    "type": "install_flatpak_yesno",
#    "value": "org.freedesktop.Platform.VulkanLayer.MangoHud",
#             (branch resolved from the app's extension points; "id//branch" forces one)
# }
# {
#    "label": "recipe_should_install_xxx",
#    "type": "install_forge_flatpak_yesno",
#    "value": "https://codeberg.org/owner/repo",   (GitHub, GitLab or Codeberg project publishing a .flatpak release asset)
# }
# Every switch (toggle, env_yesno, install_*) also accepts "default": false
# to be unchecked on install.
