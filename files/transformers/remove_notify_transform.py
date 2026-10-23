from .base_transformer import BaseTransformer


class RemoveNotifyTransformer(BaseTransformer):
    """removeNotify() (no parameters) is still a valid, public method of
    java.awt.Component in Java 21, so an override of it is valid code and must
    NOT be removed or rewritten. (Only removeNotify(ComponentPeer) is handled,
    by RemoveNotifyComponentPeerTransformer.)"""

    def transform(self, content: str):
        return content, []