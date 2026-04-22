class FrameCacheService:
    def __init__(self):
        self.cache = {}

    def get(self, obj_id):
        return self.cache.get(obj_id)

    def update(self, obj_id, data):
        self.cache[obj_id] = data

    def clear_missing(self, current_ids):
        self.cache = {
            k: v for k, v in self.cache.items()
            if k in current_ids
        }