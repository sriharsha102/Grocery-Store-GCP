import { useEffect, useRef, useState, useCallback } from 'react';

interface UseReconnectingWebSocketOptions {
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onMessage?: (event: MessageEvent) => void;
  onError?: (event: Event) => void;
  heartbeatInterval?: number; // milliseconds
  reconnectInterval?: number; // milliseconds
  maxReconnectAttempts?: number;
}

export enum WebSocketStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTING = 'reconnecting',
  FAILED = 'failed',
}

export function useReconnectingWebSocket(
  url: string,
  options: UseReconnectingWebSocketOptions = {}
) {
  const {
    onOpen,
    onClose,
    onMessage,
    onError,
    heartbeatInterval = 30000, // 30 seconds
    reconnectInterval = 2000, // 2 seconds
    maxReconnectAttempts = 10,
  } = options;

  const [status, setStatus] = useState<WebSocketStatus>(WebSocketStatus.CONNECTING);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    clearHeartbeat();
    heartbeatTimerRef.current = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          // Send ping message
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
          console.debug('[WebSocket] Heartbeat sent');
        } catch (err) {
          console.error('[WebSocket] Failed to send heartbeat:', err);
        }
      }
    }, heartbeatInterval);
  }, [heartbeatInterval, clearHeartbeat]);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.warn('[WebSocket] Already connected');
      return;
    }

    try {
      console.info(`[WebSocket] Connecting to ${url}...`);
      setStatus(
        reconnectAttemptsRef.current > 0
          ? WebSocketStatus.RECONNECTING
          : WebSocketStatus.CONNECTING
      );

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.info('[WebSocket] Connected successfully');
        setStatus(WebSocketStatus.CONNECTED);
        reconnectAttemptsRef.current = 0;
        startHeartbeat();
        onOpen?.();
      };

      ws.onclose = (event) => {
        console.warn(`[WebSocket] Closed. Code: ${event.code}, Reason: ${event.reason}`);
        clearHeartbeat();
        setStatus(WebSocketStatus.DISCONNECTED);
        onClose?.(event);

        // Attempt reconnection if it wasn't a clean close and we should reconnect
        if (shouldReconnectRef.current && event.code !== 1000) {
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current++;
            const delay = reconnectInterval * Math.pow(1.5, reconnectAttemptsRef.current - 1);
            console.info(
              `[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
            );

            clearReconnectTimer();
            reconnectTimerRef.current = setTimeout(() => {
              connect();
            }, delay);
          } else {
            console.error('[WebSocket] Max reconnection attempts reached');
            setStatus(WebSocketStatus.FAILED);
          }
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle pong response (if backend implements it)
          if (data.type === 'pong') {
            console.debug('[WebSocket] Pong received');
            return;
          }

          onMessage?.(event);
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
          onMessage?.(event); // Still pass raw event
        }
      };

      ws.onerror = (event) => {
        console.error('[WebSocket] Error occurred:', event);
        onError?.(event);
      };
    } catch (err) {
      console.error('[WebSocket] Failed to create connection:', err);
      setStatus(WebSocketStatus.FAILED);
    }
  }, [url, onOpen, onClose, onMessage, onError, startHeartbeat, clearHeartbeat, clearReconnectTimer, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    console.info('[WebSocket] Manually disconnecting');
    shouldReconnectRef.current = false;
    clearHeartbeat();
    clearReconnectTimer();

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnecting');
      wsRef.current = null;
    }

    setStatus(WebSocketStatus.DISCONNECTED);
  }, [clearHeartbeat, clearReconnectTimer]);

  const send = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        const message = typeof data === 'string' ? data : JSON.stringify(data);
        wsRef.current.send(message);
        return true;
      } catch (err) {
        console.error('[WebSocket] Failed to send message:', err);
        return false;
      }
    } else {
      console.warn('[WebSocket] Cannot send message - not connected');
      return false;
    }
  }, []);

  const reconnect = useCallback(() => {
    console.info('[WebSocket] Manual reconnection requested');
    reconnectAttemptsRef.current = 0;
    shouldReconnectRef.current = true;
    disconnect();
    setTimeout(() => connect(), 100);
  }, [connect, disconnect]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      shouldReconnectRef.current = false;
      clearHeartbeat();
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [url, connect, clearHeartbeat, clearReconnectTimer]);

  return {
    ws: wsRef.current,
    status,
    send,
    reconnect,
    disconnect,
    isConnected: status === WebSocketStatus.CONNECTED,
  };
}
