# Milky Adapter for satori-python

This adapter implements support for the Milky protocol in satori-python, allowing seamless integration with Milky-compatible chat platforms.

## Features

### Supported Adapters

- **MilkyAdapter**: Forward/client adapter that connects to Milky servers via WebSocket
- **MilkyReverseAdapter**: Reverse/server adapter that accepts connections from Milky clients

### Supported APIs

- Message operations (create, get, delete)
- Channel management (get, list)
- Guild operations (get, list)
- User information retrieval
- Friend and guild member management
- Internal Milky-specific APIs

### Supported Events

- Message events (created, deleted, updated)
- Friend requests and management
- Guild member events (join, leave)
- Guild requests
- Connection lifecycle events

### Supported Message Elements

- Text messages
- Mentions (@user)
- Images, audio, video files
- File attachments
- Custom elements

## Usage

### Forward Adapter (Client Mode)

Connect to a Milky server:

```python
from satori.server import Server
from satori.adapters.milky import MilkyAdapter

server = Server(host="localhost", port=5140)

# Create adapter that connects to Milky server
adapter = MilkyAdapter(
    endpoint="ws://milky-server:8080/ws",
    access_token="your_token_here"  # Optional
)

server.apply(adapter)
server.run()
```

### Reverse Adapter (Server Mode)

Accept connections from Milky clients:

```python
from satori.server import Server
from satori.adapters.milky import MilkyReverseAdapter

server = Server(host="localhost", port=5141)

# Create adapter that accepts Milky client connections
adapter = MilkyReverseAdapter(path="/milky")

server.apply(adapter)
server.run()
```

Milky clients can then connect to `ws://localhost:5141/milky`.

## Protocol Implementation

### Message Format

The adapter handles conversion between Satori message elements and Milky protocol format:

**Satori → Milky:**
```python
# Satori elements
[Text("Hello"), Element("at", {"id": "12345"})]

# Becomes Milky format
[
    {"type": "text", "data": {"text": "Hello"}},
    {"type": "at", "data": {"id": "12345"}}
]
```

**Milky → Satori:**
```python
# Milky format
[
    {"type": "text", "data": {"text": "Hello"}},
    {"type": "image", "data": {"url": "https://example.com/image.png"}}
]

# Becomes Satori elements  
[Text("Hello"), Element("img", {"src": "https://example.com/image.png"})]
```

### Event Handling

The adapter supports the following event types:

- `message.created` - New message received
- `message.deleted` - Message deleted
- `request.friend` - Friend request received
- `request.guild.invite` - Guild invitation received
- `request.guild.join` - Guild join request
- `notice.member.join` - Member joined guild
- `notice.member.leave` - Member left guild
- `notice.friend.add` - Friend added
- `notice.friend.remove` - Friend removed

### API Mapping

Common Satori APIs are mapped to Milky protocol calls:

- `message.create` → `send_message`
- `message.get` → `get_message`
- `message.delete` → `delete_message`
- `channel.get` → `get_channel_info`
- `channel.list` → `get_channel_list`
- `guild.get` → `get_guild_info`
- `guild.list` → `get_guild_list`
- `user.get` → `get_user_info`

## Configuration

### MilkyAdapter Options

- `endpoint`: WebSocket endpoint URL of the Milky server
- `access_token`: Optional authentication token

### MilkyReverseAdapter Options

- `path`: WebSocket endpoint path (default: "/milky")

## Development

The adapter follows the same patterns as other satori-python adapters:

- `main.py` - Forward adapter implementation
- `reverse.py` - Reverse adapter implementation  
- `api.py` - API route handling
- `message.py` - Message serialization/deserialization
- `utils.py` - Utility functions and protocol helpers
- `events/` - Event handler implementations

## Compatibility

This adapter is designed to be compatible with:

- Milky protocol specification
- Standard Satori protocol features
- Existing satori-python server infrastructure

## Example

See `example/milky_adapter_example.py` for a complete usage example.