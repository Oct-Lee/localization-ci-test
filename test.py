#!/bin/bash


# get script path, follow symlink
SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")
cd $SCRIPTPATH

UNITX_HOME=/home/unitx
LOG_DIR=$UNITX_HOME/unitx_data/logs
LOG_FILE=$LOG_DIR/prod.log
mkdir -p "$LOG_DIR"
if [ ! -f $LOG_FILE ]; then
  touch $LOG_FILE
  chmod 777 $LOG_FILE
fi

# Prevent duplicate clicks
LOCK_FILE="${UNITX_HOME}/prod_run.lock"
export LOCK_FILE
if [ -f "$LOCK_FILE" ]; then
  echo "ProdX run.sh is already running (lock file exists)." >> $LOG_DIR/prod.log
  exit 1
fi

# Check if backtest_prod container is running (mutual exclusion)
if docker ps --format "table {{.Names}}" | grep -q "backtest_prod"; then
  echo "Evrror: backtest_prod container is already raunning. Cannot start ProdX container." >> $LOG_DIR/prod.log
  echo "Please stop backtest_prod first using: ./stop_backtest.sh"
  exit 1
fi

touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

export CURRENT_USER=$(whoami)

/usr/bin/python3 "$UNITX_HOME/prod/production/boot_check/boot_popup_gui.py" &

UNITX_CONTAINER_NAME=${UNITX_CONTAINER_NAME:-unitx_runtime}
if docker --version && docker images | grep -q "$UNITX_CONTAINER_NAME"; then
  xhost +local:docker
  if docker ps --format "{{.Names}}" | grep -q "^prod$"; then
    echo "ProdX container is already running, skipping stop/run"
    exit 0
  fi
  docker stop prod
  docker wait prod
  if [ ! -f /usr/lib/libidlLinux.so.1 ]; then
    docker run --rm \
      --name prod \
      --log-driver=none \
      --ipc=host \
      --network=host \
      --pid=host \
      --privileged \
      --gpus all \
      --user unitx \
      -e DBUS_SESSION_BUS_ADDRESS \
      -e DISPLAY \
      -e LOCK_FILE \
      -e "HOME=$UNITX_HOME" \
      -e "CURRENT_USER=$CURRENT_USER" \
      -e "TIMM_USE_OLD_CACHE=1" \
      -e "TZ=$(cat /etc/timezone)" \
      -e MVCAM_SDK_PATH=/opt/MVS \
      -e MVCAM_COMMON_RUNENV=/opt/MVS/lib \
      -e LD_LIBRARY_PATH=/opt/MVS/lib/64 \
      -e RUNTIME_MODE=$RUNTIME_MODE \
      -v "$UNITX_HOME:$UNITX_HOME:shared" \
      -v "/home/factory:/home/factory:shared" \
      -v /tmp/.X11-unix:/tmp/.X11-unix \
      -v /media:/media \
      -v /etc/machine-id:/etc/machine-id:ro \
      -v /run/user/$(id -u)/bus:/run/user/$(id -u)/bus \
      -v /dev/bus:/dev/bus \
      "$UNITX_CONTAINER_NAME" \
      "$UNITX_HOME/prod/production/start_everything.sh"
  else
        docker run --rm \
      --name prod \
      --log-driver=none \
      --ipc=host \
      --network=host \
      --pid=host \
      --privileged \
      --gpus all \
      --user unitx \
      -e DBUS_SESSION_BUS_ADDRESS \
      -e DISPLAY \
      -e LOCK_FILE \
      -e "HOME=$UNITX_HOME" \
      -e "CURRENT_USER=$CURRENT_USER" \
      -e "TIMM_USE_OLD_CACHE=1" \
      -e "TZ=$(cat /etc/timezone)" \
      -e MVCAM_SDK_PATH=/opt/MVS \
      -e MVCAM_COMMON_RUNENV=/opt/MVS/lib \
      -e LD_LIBRARY_PATH=/opt/MVS/lib/64 \
      -e RUNTIME_MODE=$RUNTIME_MODE \
      -v "$UNITX_HOME:$UNITX_HOME:shared" \
      -v "/home/factory:/home/factory:shared" \
      -v /tmp/.X11-unix:/tmp/.X11-unix \
      -v /media:/media \
      -v /etc/machine-id:/etc/machine-id:ro \
      -v /run/user/$(id -u)/bus:/run/user/$(id -u)/bus \
      -v /dev/bus:/dev/bus \
      -v /usr/lib/libidl115DriverLinux.so.1:/usr/lib/libidl115DriverLinux.so.1 \
      -v /usr/lib/libidlLinux.so.1:/usr/lib/libidlLinux.so.1 \
      "$UNITX_CONTAINER_NAME" \
      "$UNITX_HOME/prod/production/start_everything.sh"
  fi
else
  echo "Docker is not installed"
  ./start_everything.sh
fi
