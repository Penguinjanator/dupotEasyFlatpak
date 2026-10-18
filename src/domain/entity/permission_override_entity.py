class PermissionOverrideEntity:

    FIELD_LABEL = "label"
    FIELD_TYPE = "type"
    FIELD_VALUE = "value"
    FIELD_SUB_VALUE_YES_NO = "subValueYesNo"

    SUB_VALUE_YES = "yes"
    TYPE_FILESYSTEM = "filesystem"
    TYPE_FILESYSTEM_NO_PROMPT = "filesystem_noprompt"
    TYPE_INSTALL_YES_NO = "install_flatpak_yesno"
    TYPE_INSTALL_FORGE_YES_NO = "install_forge_flatpak_yesno"
    TYPE_SOUND = "sound"

    DEFAULT_SOUND_SOCKET = "pulseaudio"

    label: str
    _type: str
    _value: str = ""
    _sub_value_yes_no: str

    def __init__(self, raw_obj: object):

        if self.FIELD_LABEL in raw_obj:
            self._label = raw_obj[self.FIELD_LABEL]
        if self.FIELD_TYPE in raw_obj:
            self._type = raw_obj[self.FIELD_TYPE]
        if self.FIELD_VALUE in raw_obj:
            self._value = raw_obj[self.FIELD_VALUE]

        pass

    def is_filesystem(self) -> bool:
        return self._type == self.TYPE_FILESYSTEM

    def is_filesystem_no_prompt(self) -> bool:
        return self._type == self.TYPE_FILESYSTEM_NO_PROMPT

    def is_sound(self) -> bool:
        return self._type == self.TYPE_SOUND

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

    def get_sub_value_yes_no(self) -> str:
        return self._sub_value_yes_no


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
#    "label": "recipe_should_install_xxx",
#    "type": "install_forge_flatpak_yesno",
#    "value": "https://codeberg.org/owner/repo",   (GitHub, GitLab or Codeberg project publishing a .flatpak release asset)
# }
