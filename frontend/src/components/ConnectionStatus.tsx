import { WebSocketStatus } from "@/hooks/useReconnectingWebSocket";

interface ConnectionStatusProps {
  status: WebSocketStatus;
}

export function ConnectionStatus({ status }: ConnectionStatusProps) {
  const getStatusConfig = () => {
    switch (status) {
      case WebSocketStatus.CONNECTED:
        return {
          color: 'bg-green-500',
          text: 'Connected',
          icon: '●',
          visible: false, // Don't show when connected (clean UI)
        };
      case WebSocketStatus.CONNECTING:
        return {
          color: 'bg-yellow-500',
          text: 'Connecting...',
          icon: '●',
          visible: true,
        };
      case WebSocketStatus.RECONNECTING:
        return {
          color: 'bg-orange-500',
          text: 'Reconnecting...',
          icon: '●',
          visible: true,
        };
      case WebSocketStatus.DISCONNECTED:
        return {
          color: 'bg-red-500',
          text: 'Disconnected',
          icon: '●',
          visible: true,
        };
      case WebSocketStatus.FAILED:
        return {
          color: 'bg-red-700',
          text: 'Connection Failed',
          icon: '✕',
          visible: true,
        };
      default:
        return {
          color: 'bg-gray-500',
          text: 'Unknown',
          icon: '●',
          visible: true,
        };
    }
  };

  const config = getStatusConfig();

  if (!config.visible) {
    return null;
  }

  return (
    <div className="fixed top-4 right-4 z-50 flex items-center gap-2 px-3 py-2 bg-background/95 backdrop-blur-sm border border-border rounded-lg shadow-lg">
      <span className={`${config.color} w-2 h-2 rounded-full animate-pulse`}></span>
      <span className="text-sm font-medium text-foreground">{config.text}</span>
    </div>
  );
}
