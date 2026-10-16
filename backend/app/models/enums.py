import enum


class UserRole(str, enum.Enum):
    TRADER = "TRADER"
    ADMIN = "ADMIN"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class TradeSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class MetricCode(str, enum.Enum):
    PNL = "PNL"
    WIN_RATE = "WIN_RATE"
    EXPOSURE = "EXPOSURE"
    LOSS_CHASING = "LOSS_CHASING"
