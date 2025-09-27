#!/usr/bin/env python3
"""
Example usage of the Milky adapter for satori-python.

This demonstrates how to set up both forward and reverse Milky adapters.
"""

import sys
import os

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from satori import Api, Channel, ChannelType
from satori.server import Response, Server
from satori.adapters.milky import MilkyAdapter, MilkyReverseAdapter


def create_server_with_forward_adapter():
    """Create a server with MilkyAdapter (forward/WebSocket client)."""
    server = Server(host="localhost", port=5140, path="")
    
    # Create milky adapter that connects to a milky server
    milky_adapter = MilkyAdapter(
        endpoint="ws://localhost:8080/milky",  # Milky server WebSocket endpoint
        access_token="your_token_here"  # Optional access token
    )
    
    server.apply(milky_adapter)
    
    @server.route(Api.CHANNEL_GET)
    async def handle_channel_get(*args, **kwargs):
        return Channel("1234567890", ChannelType.TEXT, "test").dump()
    
    return server


def create_server_with_reverse_adapter():
    """Create a server with MilkyReverseAdapter (reverse/WebSocket server)."""
    server = Server(host="localhost", port=5141, path="")
    
    # Create reverse milky adapter that accepts connections from milky clients
    milky_reverse_adapter = MilkyReverseAdapter(
        path="/milky"  # WebSocket endpoint path
    )
    
    server.apply(milky_reverse_adapter)
    
    @server.route(Api.CHANNEL_GET)
    async def handle_channel_get(*args, **kwargs):
        return Channel("1234567890", ChannelType.TEXT, "test").dump()
    
    return server


if __name__ == "__main__":
    import asyncio
    
    print("Milky Adapter Example")
    print("1. Forward adapter (connects to milky server)")
    print("2. Reverse adapter (accepts milky client connections)")
    
    choice = input("Choose adapter type (1 or 2): ").strip()
    
    if choice == "1":
        print("Starting server with MilkyAdapter...")
        print("This will try to connect to ws://localhost:8080/milky")
        server = create_server_with_forward_adapter()
    elif choice == "2":
        print("Starting server with MilkyReverseAdapter...")
        print("Milky clients can connect to ws://localhost:5141/milky")
        server = create_server_with_reverse_adapter()
    else:
        print("Invalid choice")
        sys.exit(1)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nServer stopped.")