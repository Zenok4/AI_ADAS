from threading import Lock

_current_state = {}
_lock = Lock()


def set_vehicle_state(state: dict) -> None:
    with _lock:
        _current_state.clear()
        _current_state.update(state or {})


def get_vehicle_state() -> dict:
    with _lock:
        return dict(_current_state)
