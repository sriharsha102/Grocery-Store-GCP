class ChatState:
    """State management for chat sessions. Note: PayPal support removed."""

    def __init__(self):
        self.customer_id = None
        self.is_guest = True
        self.cart = {}
        self.websocket = None
        self.stripe_order_id = None
        self.item_tab_mapping = {}  # Maps item_name -> tab_name for multi-tab inventory
        self.active_tabs = []
        self.weight_cache = {}
        self.weight_cache_ts = 0.0
        self.awaiting_email = False

    def reset(self):
        self.customer_id = None
        self.is_guest = True
        self.cart = {}
        self.websocket = None
        self.stripe_order_id = None
        self.item_tab_mapping = {}
        self.active_tabs = []
        self.weight_cache = {}
        self.weight_cache_ts = 0.0
        self.awaiting_email = False

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "is_guest": self.is_guest,
            "cart": self.cart,
            "websocket": self.websocket,
            "stripe_order_id": self.stripe_order_id,
            "item_tab_mapping": self.item_tab_mapping,
            "active_tabs": self.active_tabs,
            "weight_cache": self.weight_cache,
            "weight_cache_ts": self.weight_cache_ts,
            "awaiting_email": self.awaiting_email,
        }

    @classmethod
    def from_dict(cls, data):
        instance = cls()
        instance.customer_id = data.get("customer_id")
        instance.is_guest = bool(data.get("is_guest", True))
        instance.cart = data.get("cart")
        instance.websocket = data.get("websocket")
        instance.stripe_order_id = data.get("stripe_order_id")
        instance.item_tab_mapping = data.get("item_tab_mapping", {})
        instance.active_tabs = data.get("active_tabs", [])
        instance.weight_cache = data.get("weight_cache", {})
        instance.weight_cache_ts = data.get("weight_cache_ts", 0.0)
        instance.awaiting_email = bool(data.get("awaiting_email", False))
        return instance
