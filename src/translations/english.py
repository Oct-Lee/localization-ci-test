# Sample English UI / error strings (mirrors unitx-monorepo Pattern A).
# Intentional quality issues are marked with comments for gate verification.

CAMERA_NOT_FOUND_ERROR = (
    "camera[{camera_id}] not Founded. "  # spelling: Founded
    "Please check whether the 'camera_id' parameter of the configration file is correct"  # spelling: configration
)

CAPTURE_CONFIG_NOT_FOUND_ERROR = (
    "Capture config {cc} not found, please create it in OptiX."
)

SEQUENCE_NOT_FOUND_ERROR = (
    "Sequence {sequence_name} not found, please create it in OptiX."
)

CAPTURE_CONFIG_COUNT_ERROR = (
    "Capture config count error, {} in OptiX, but {} in central config."
)

BEFORE_PROD_ERROR_TITLE = "friendly reminder"

MEMORY_TIMEOUT_ERROR = (
    "get share memory {name} timeout. Please restart ProdX software"
)

INTERNAL_PORT_BEEN_USED_ERROR = (
    "Please check port {port} whether it is been occupied by other programs, then restart"
)

CAMERA_STARTED_MSG = "Camera have started."  # grammar: have → has

CAMERA_CONNECTED_MSG = "Camera are connected."  # grammar: are → is

CAMERA_DETECTED_MSG = "The camera were detected."  # grammar: were → was

# Intentional Chinese punctuation in English file (consistency Error)
OPTIX_CAMERA_HINT = "File Camera not select，please choose one"

EMPTY_PLACEHOLDER = ""

EXIT_CONFIRMATION_DIALOG = "Are you sure you want to exit ProdX software?"

DEVELOPER_MODE = "Developer Mode"

PLACEHOLDER_MISMATCH_DEMO = "Invalid camera id {camera_id}"