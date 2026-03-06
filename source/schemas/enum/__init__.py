from enum import StrEnum


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    ABOUT_TO_START = "about_to_start"
    LIVE = "live"
    FINISHED = "finished"
    RETIRED = "retired"
    WALKOVER = "walkover"


class UserRole(StrEnum):
    GUEST = "guest"
    USER = "user"
    EDITOR = "editor"
    OPERATOR = "operator"
    ADMIN = "admin"
