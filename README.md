# Ready Redis

Ready Redis is a Python library that provides an embedded Redis instance using TestContainers. It allows you to quickly set up and use a Redis client without having Redis installed on your system.

## Installation

```bash
pip install ready-redis
```

## Usage

```py
from ready_redis import ReadyRedis

# Get a Redis client with default settings
with ReadyRedis.get() as r:
    r.set('foo', 'bar')
    print(r.get('foo'))  # b'bar'

# Get a Redis client with custom settings
with ReadyRedis.get(port=5678, protocol=3, redis_version="6.2", redis_args="--maxmemory 100mb") as r:
    r.set('hello', 'world')
    print(r.get('hello'))  # b'world'

# Test ReadyRedis without with and manual cleanup
r = ReadyRedis.get(redis_container_name="my-redis", port=6383)
client = r.client
client.set('hello', 'world')
print(client.get('hello'))  # b'world'
r.cleanup()
```

## Google Colab

See [sample notebook](https://colab.research.google.com/drive/1dBgzXVuxsBWoMVIunG7YzEb4nnTaC32v?usp=sharing)

## Features
- Embedded Redis instance using TestContainers
- Customizable Redis version and arguments
- Easy-to-use interface with `redis-py` compatibility
- Singleton pattern to ensure a single Redis instance per configuration


# Build and test the package:

```bash
poetry build
poetry run pytest
```

