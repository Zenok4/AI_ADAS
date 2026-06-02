from flask import Blueprint, request, jsonify
from app.state import set_vehicle_state

vehicle_state_bp = Blueprint('vehicle_state', __name__)


@vehicle_state_bp.route('/state', methods=['POST'])
def post_state():
    data = request.get_json(force=True)
    # accept yaw_rate and steering_angle (and any other fields)
    state = {}
    if not isinstance(data, dict):
        return jsonify({'error': 'invalid payload'}), 400
    # copy allowed keys
    for k in ('yaw_rate', 'steering_angle'):
        if k in data:
            try:
                state[k] = float(data[k])
            except Exception:
                state[k] = data[k]
    # include all keys too
    for k, v in data.items():
        if k not in state:
            state[k] = v

    set_vehicle_state(state)
    return jsonify({'status': 'ok', 'state': state})
