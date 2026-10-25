"""Connection transitions, independent of GUI widgets and refresh frequency."""
class ConnectionNoticePolicy:
    def __init__(self):
        self.last_token=None

    def observe(self,ready,token,*,busy=False,enabled=True):
        if not ready:
            self.last_token=None
            return False
        if busy:
            return False
        changed=token!=self.last_token
        self.last_token=token
        return changed and enabled
