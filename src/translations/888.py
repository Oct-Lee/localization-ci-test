# Sample English UI / error strings (mirrors unitx-monorepo Pattern A).
# Intentional quality issues are marked with comments for gate verification.

CAMERA_NOT_FOUND_ERROR = (
    "camera[{camera_id}] not Founded. "  # wrong word (Founded); LT/cspell may differ
    "Please check whether the 'camera_id' parameter oef the configration fisle is correct"  # spelling: configration, fisle
)

CAMERA_STARTED_MSG = "Cuamera have started."  # may not be caught by free LT rules
PORT_BUSY_ERROR = (
    "Please check port {port} whether it is been occupied by other programs"
)  # grammar: is been → has been / is being

DEVELOPER_MODE = "Developer Mode"

PLACEHOLDER_MISMATCH_DEMO = "Invalid camera id {camera_id}"
