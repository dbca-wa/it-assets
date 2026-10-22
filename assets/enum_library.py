class Severity:
    """Enum class for the Vulnerability field "severity" """

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SeverityMT:
    """Enum class for the Vulnerability field "severity_modification_type" """

    NONE = "N"
    RECASTED = "R"
    ACCEPTED = "A"


class State:
    """Enum class for the Vulnerability field "state" """

    OPEN = "O"
    REOPENED = "R"
    FIXED = "F"
