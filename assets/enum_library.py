class Severity:
    """Enum class for the Vulnerability field 'severity' """

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SeverityMT:
    """Enum class for the Vulnerability field 'severity_modification_type' """

    NONE = "N"
    RECASTED = "R"
    ACCEPTED = "A"


class State:
    """Enum class for the Vulnerability field 'state' """

    OPEN = "O"
    REOPENED = "R"
    FIXED = "F"

class ProjectStatus:
    """Enum class for Project field 'project_status'"""
    UNKNOWN = 0
    A2_PRE_DISCOVERY = 1
    A2_SHORT_PROCESS = 2
    B1_DISCOVERY = 3
    B2_DELIVERY = 4
    B3_CLOSURE = 5
    CANCELLED = 6
    NOT_STARTED = 7
