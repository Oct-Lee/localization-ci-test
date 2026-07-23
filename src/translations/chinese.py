# Sample Chinese UI / error strings (mirrors unitx-monorepo Pattern A).

CAMERA_NOT_FOUND_ERROR = (
    "没有找到相机[{camera_id}]，请检查配置文件的camera_id参数是否正确"
)

CAPTURE_CONFIG_NOT_FOUND_ERROR = "采像设置 {cc} 不存在, 请在 OptiX 中创建它。"

SEQUENCE_NOT_FOUND_ERROR = "序列 {sequence_name} 不存在, 请在 OptiX 中创建它。"

CAPTURE_CONFIG_COUNT_ERROR = (
    "采像设置数量不对, 在OptiX中有{}个, 但是在Central中配置了{}个"
)

BEFORE_PROD_ERROR_TITLE = "友情提示"

MEMORY_TIMEOUT_ERROR = "加载共享内存{name}超时, 请重启'ProdX'软件"

INTERNAL_PORT_BEEN_USED_ERROR = "请检查端口{port}是否被其它程序占用,然后重启软件"

CAMERA_STARTED_MSG = "相机已启动。"

CAMERA_CONNECTED_MSG = "相机已连接。"

CAMERA_DETECTED_MSG = "已检测到相机。"

OPTIX_CAMERA_HINT = "未选择文件相机，请选择一个"

EMPTY_PLACEHOLDER = "占位"

EXIT_CONFIRMATION_DIALOG = "您确定要退出生产软件吗？"

DEVELOPER_MODE = "开发者模式"

# Intentional missing key relative to english is demonstrated by
# MISSING_IN_CHINESE_ONLY being absent; english has all shared keys.
# Intentional placeholder mismatch for gate verification:
PLACEHOLDER_MISMATCH_DEMO = "相机编号错误"  # english has {camera_id}
