class ChatState:
    """State management for chat sessions. Note: PayPal support removed."""

    def __init__(self):
        self.customer_id = None
        self.is_guest = True
        self.cart = {}
        self.websocket = None
        self.stripe_order_id = None

    def reset(self):
        self.customer_id = None
        self.is_guest = True
        self.cart = {}
        self.websocket = None
        self.stripe_order_id = None

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "is_guest": self.is_guest,
            "cart": self.cart,
            "websocket": self.websocket,
            "stripe_order_id": self.stripe_order_id,
        }

    @classmethod
    def from_dict(cls, data):
        instance = cls()
        instance.customer_id = data.get("customer_id")
        instance.is_guest = bool(data.get("is_guest", True))
        instance.cart = data.get("cart")
        instance.websocket = data.get("websocket")
        instance.stripe_order_id = data.get("stripe_order_id")
        return instance
