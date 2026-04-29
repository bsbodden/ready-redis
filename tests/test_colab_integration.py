"""Integration tests using Google Colab Docker runtime image and TestContainers."""

import time

import pytest
import redis
from testcontainers.compose import DockerCompose


class TestColabDockerIntegration:
    """Integration tests using Google Colab's official Docker runtime image."""
    
    @pytest.mark.slow
    def test_redis_with_testcontainers_compose(self, tmp_path):
        """Test Redis using TestContainers compose with actual container."""
        # Use standard Redis image which is much smaller than Colab image
        compose_content = """
version: '3.8'
services:
  redis:
    image: redis:7.2-alpine
    container_name: test-redis-compose
    ports:
      - "7300:6379"
    command: redis-server --maxmemory 50mb --maxmemory-policy allkeys-lru
"""
        compose_file = tmp_path / "docker-compose-test.yml"
        compose_file.write_text(compose_content)
        
        compose = DockerCompose(
            context=str(tmp_path),
            compose_file_name="docker-compose-test.yml"
        )
        
        try:
            compose.start()
            container = compose.get_container("redis")
            assert container.State == "running"
            
            # Wait for Redis to be ready
            time.sleep(3)
            
            # Connect to Redis
            client = redis.Redis(host="localhost", port=7300)
            assert client.ping()
            
            # Verify configuration
            config = client.config_get("maxmemory")
            assert int(config["maxmemory"]) == 52428800  # 50MB in bytes
            
        finally:
            compose.stop()
    
    @pytest.mark.slow
    def test_colab_redis_appimage_installation(self, tmp_path):
        """Test Redis Stack AppImage download and installation like in Colab."""
        # Create compose file without version (deprecated) and with healthcheck
        compose_content = """
services:
  colab-redis:
    image: ubuntu:22.04
    container_name: test-colab-redis
    command: >
      /bin/bash -c "
      echo 'Installing dependencies...' &&
      apt-get update &&
      apt-get install -y wget ca-certificates &&
      echo 'Downloading Redis Stack AppImage...' &&
      wget https://packages.redis.io/redis-stack/redis-stack-server-7.2.0-v2-x86_64.AppImage &&
      chmod +x redis-stack-server-7.2.0-v2-x86_64.AppImage &&
      echo 'Starting Redis Stack with extraction mode...' &&
      APPIMAGE_EXTRACT_AND_RUN=1 ./redis-stack-server-7.2.0-v2-x86_64.AppImage --port 6379 --bind 0.0.0.0 --maxmemory 100mb --maxmemory-policy allkeys-lru
      "
    ports:
      - "7302:6379"
    environment:
      - APPIMAGE_EXTRACT_AND_RUN=1
    healthcheck:
      test: ["CMD", "echo", "1"]
      interval: 5s
      timeout: 3s
      retries: 60
"""
        compose_file = tmp_path / "docker-compose-colab.yml"
        compose_file.write_text(compose_content)
        
        # Use subprocess directly to avoid the --wait issue
        import subprocess
        
        try:
            # Start the container without --wait
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "up", "-d"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Docker compose failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, result.args)
            
            # Verify container is running
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=test-colab-redis", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                check=True
            )
            assert "Up" in result.stdout
            
            # Wait for AppImage download and Redis Stack to start
            # AppImage download can take 30-60 seconds depending on network
            max_wait = 180  # 3 minutes max for download + startup
            client = redis.Redis(host="localhost", port=7302, socket_connect_timeout=2)
            
            print("Waiting for Redis Stack AppImage to download and start...")
            for i in range(max_wait):
                time.sleep(1)
                try:
                    if client.ping():
                        print(f"Redis Stack ready after {i+1} seconds")
                        break
                except (redis.ConnectionError, redis.TimeoutError):
                    if i % 15 == 0 and i > 0:
                        print(f"Still waiting... ({i} seconds elapsed)")
                    continue
            else:
                # If we get here, Redis didn't start after max_wait seconds
                raise TimeoutError(f"Redis Stack failed to start after {max_wait} seconds")
            
            assert client.ping()
            
            # Set and get data
            client.set("colab_test", "success")
            assert client.get("colab_test") == b"success"
            
            # Verify Redis is configured correctly - Redis-py 5.x returns string keys
            config = client.config_get("maxmemory")
            assert config.get("maxmemory") == "104857600"  # 100MB in bytes as string
            
        finally:
            # Stop and remove the container
            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "down"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True
            )


class TestDockerComposeWithCustomRedis:
    """Test using DockerCompose directly with custom Redis setup."""
    
    @pytest.fixture
    def redis_compose_file(self, tmp_path):
        """Create a custom Docker Compose file for Redis."""
        compose_content = """
version: '3.8'
services:
  redis:
    image: redis:7.2
    container_name: test-custom-redis
    ports:
      - "7210:6379"
    command: redis-server --maxmemory 100mb --maxmemory-policy allkeys-lru
"""
        compose_file = tmp_path / "docker-compose-redis.yml"
        compose_file.write_text(compose_content)
        return compose_file
    
    def test_custom_redis_with_docker_compose(self, redis_compose_file):
        """Test custom Redis configuration with DockerCompose."""
        compose = DockerCompose(
            context=str(redis_compose_file.parent),
            compose_file_name=redis_compose_file.name
        )
        
        try:
            compose.start()
            container = compose.get_container("redis")
            assert container.State == "running"
            
            # Connect and verify configuration
            time.sleep(2)  # Wait for Redis to start
            
            client = redis.Redis(host="localhost", port=7210)
            assert client.ping()
            
            # Verify custom config - Redis-py 5.x returns string keys
            config = client.config_get("maxmemory")
            assert config.get("maxmemory") == "104857600"  # 100MB in bytes as string
            
            policy = client.config_get("maxmemory-policy")
            assert policy.get("maxmemory-policy") == "allkeys-lru"
            
        finally:
            compose.stop()