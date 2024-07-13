import pytest

from ready_redis import ReadyRedis


def test_ready_redis():
    """Test the ReadyRedis singleton instance with basic Redis commands."""
    with ReadyRedis.get(port=6380) as redis:
        assert redis.ping()

        redis.set("foo", "bar")
        assert redis.get("foo") == b"bar"

        # You can use any Redis method directly
        redis.lpush("mylist", 1, 2, 3)
        assert redis.lrange("mylist", 0, -1) == [b"3", b"2", b"1"]


def test_ready_redis_custom_params():
    """Test the ReadyRedis singleton instance with custom parameters."""
    with ReadyRedis.get(
        port=6381, protocol=3, redis_version="6.2.6-v9", redis_args="--maxmemory 100mb"
    ) as r:
        assert r.ping()

        r.set("hello", "world")
        assert r.get("hello") == b"world"


def test_ready_redis_singleton():
    """Test that ReadyRedis.get() returns the same instance (singleton)."""
    project_name = "test-singleton-project"
    container_name = "test-singleton-redis"
    port = 6382

    r1 = ReadyRedis.get(
        name=project_name, redis_container_name=container_name, port=port
    )
    r2 = ReadyRedis.get(
        name=project_name, redis_container_name=container_name, port=port
    )

    assert (
        r1 is r2
    ), "ReadyRedis.get() should return the same instance for the same configuration"

    # Verify that a different configuration returns a different instance
    r3 = ReadyRedis.get(
        name=project_name, redis_container_name="different-container", port=port
    )
    assert (
        r1 is not r3
    ), "ReadyRedis.get() should return a different instance for a different configuration"


def test_ready_redis_with_custom_container_project_name():
    """Test ReadyRedis with a custom project name."""
    with ReadyRedis.get(name="bsb-playground") as r:
        assert r.ping()

        r.set("foo", "bar")
        assert r.get("foo") == b"bar"


def test_ready_redis_with_custom_redis_container_name():
    """Test ReadyRedis with a custom Redis container name."""
    with ReadyRedis.get(redis_container_name="my-redis") as r:
        assert r.ping()

        r.set("foo", "bar")
        assert r.get("foo") == b"bar"


def test_manual_cleanup():
    """Test ReadyRedis without with and manual cleanup."""
    r = ReadyRedis.get(redis_container_name="my-redis", port=6383)
    assert r.client.ping()

    r.cleanup()
