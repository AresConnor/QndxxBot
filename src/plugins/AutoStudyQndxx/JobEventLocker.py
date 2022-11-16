class JobEventLocker:
    def __init__(self, lockedEvent=None):
        self.LockedEvent = lockedEvent
        self.Locked = False
