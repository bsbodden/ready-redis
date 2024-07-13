import atexit
import importlib.resources
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import redis
import requests
from testcontainers.compose import DockerCompose
from tqdm import tqdm
from ulid import ULID


def is_colab_environment():
    try:
        import google.colab

        return True
    except ImportError:
        return False


class ColabRedis:
    REDIS_STACK_VERSION = "7.2.0-v2"
    REDIS_STACK_IMAGE = f"redis-stack-server-{REDIS_STACK_VERSION}-x86_64.AppImage"
    REDIS_STACK_URL = f"https://packages.redis.io/redis-stack/{REDIS_STACK_IMAGE}"

    def __init__(self, port, redis_args):
        self.port = port
        self.redis_args = redis_args
        self.process = None

    def start(self):
        print(
            f"Google Colab environment detected. Installing Redis Stack v{self.REDIS_STACK_VERSION}..."
        )

        try:
            self._download_redis_stack()
            self._install_and_run_redis_stack()
            print("Redis Stack installation completed successfully.")
        except Exception as e:
            print(f"Error during Redis Stack installation: {str(e)}")
            raise

    def _download_redis_stack(self):
        response = requests.get(self.REDIS_STACK_URL, stream=True)
        total_size = int(response.headers.get("content-length", 0))

        with open(self.REDIS_STACK_IMAGE, "wb") as file, tqdm(
            desc="Downloading Redis Stack",
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as progress_bar:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                progress_bar.update(size)

    def _install_and_run_redis_stack(self):
        commands = [
            f"chmod a+x {self.REDIS_STACK_IMAGE}",
            f"./{self.REDIS_STACK_IMAGE} --port {self.port} {self.redis_args} --daemonize yes",
            "sleep 2",
        ]

        for cmd in tqdm(commands, desc="Setting up Redis Stack"):
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Command failed: {cmd}\nError: {result.stderr}")
            time.sleep(0.5)  # Add a small delay to make the progress bar more visible

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()


class ReadyRedis:
    _instances: Dict[Tuple, "ReadyRedis"] = {}

    @classmethod
    def get(
        cls,
        name: str = "ready-redis",
        redis_container_name: Optional[str] = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        protocol: int = 3,
        redis_version: str = "latest",
        redis_args: str = "--save '' --appendonly no",
    ):
        if redis_container_name is None:
            redis_container_name = f"redis-stack-{str(ULID())}"

        config = (
            name,
            redis_container_name,
            host,
            port,
            db,
            password,
            protocol,
            redis_version,
            redis_args,
        )
        if config not in cls._instances:
            cls._instances[config] = cls(
                name,
                redis_container_name,
                host,
                port,
                db,
                password,
                protocol,
                redis_version,
                redis_args,
            )
        return cls._instances[config]

    def __init__(
        self,
        name: str,
        redis_container_name: str,
        host: str,
        port: int,
        db: int,
        password: Optional[str],
        protocol: int,
        redis_version: str,
        redis_args: str,
    ):
        self._name = name
        self._redis_container_name = redis_container_name
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._protocol = protocol
        self._redis_version = redis_version
        self._redis_args = redis_args
        self._compose = None
        self._env_file = None
        self._cleaned_up = False
        self._colab_redis = None

        if is_colab_environment():
            self._start_colab_redis()
        else:
            self._start_redis_container()

        self._client = redis.Redis(
            host=self._host,
            port=self._port,
            db=self._db,
            password=self._password,
            protocol=self._protocol,
        )
        atexit.register(self.cleanup)

    def _start_colab_redis(self):
        self._colab_redis = ColabRedis(self._port, self._redis_args)
        try:
            self._colab_redis.start()
        except Exception as e:
            print(f"Failed to start Redis Stack in Colab environment: {str(e)}")
            raise

    def _start_redis_container(self):
        try:
            # Try to find the docker-compose.yml file in the package
            compose_file = (
                importlib.resources.files("ready_redis") / "docker-compose.yml"
            )
            if not compose_file.is_file():
                raise FileNotFoundError(
                    f"docker-compose.yml not found at {compose_file}"
                )
        except ImportError:
            # Fallback for development mode
            current_dir = Path(__file__).parent.absolute()
            project_root = current_dir.parent
            compose_file = project_root / "docker-compose.yml"

        if not Path(compose_file).is_file():
            raise FileNotFoundError(f"docker-compose.yml not found at {compose_file}")

        self._env_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".env"
        )
        self._env_file.write(f"PROJECT_NAME={self._name}\n")
        self._env_file.write(f"REDIS_CONTAINER_NAME={self._redis_container_name}\n")
        self._env_file.write(f"REDIS_VERSION={self._redis_version}\n")
        self._env_file.write(f"REDIS_PORT={self._port}\n")
        self._env_file.write(f"REDIS_ARGS={self._redis_args}\n")
        self._env_file.flush()

        self._compose = DockerCompose(
            context=str(Path(compose_file).parent),
            compose_file_name=Path(compose_file).name,
            env_file=self._env_file.name,
        )

        try:
            self._compose.start()
        except subprocess.CalledProcessError as e:
            if "manifest unknown" in str(e):
                print(
                    f"Warning: Redis version {self._redis_version} not found. Falling back to latest."
                )
                self._redis_version = "latest"
                self._env_file.seek(0)
                self._env_file.write(f"REDIS_VERSION=latest\n")
                self._env_file.truncate()
                self._env_file.flush()
                self._compose.start()
            else:
                raise

    def cleanup(self):
        if self._cleaned_up:
            return

        if self._colab_redis:
            print("Stopping Redis Stack in Google Colab environment...")
            self._colab_redis.stop()
            print("Redis Stack stopped.")
        elif self._compose and sys.meta_path is not None:
            try:
                self._compose.stop()
            except Exception as e:
                print(f"Error during cleanup: {e}")

        if self._env_file:
            self._env_file.close()
            try:
                os.unlink(self._env_file.name)
            except FileNotFoundError:
                pass

        self._cleaned_up = True

    def __del__(self):
        self.cleanup()

    def __enter__(self):
        return self._client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    @classmethod
    def shutdown_all(cls):
        for instance in cls._instances.values():
            instance.cleanup()
        cls._instances.clear()

    @property
    def container_name(self):
        return self._redis_container_name

    @property
    def client(self):
        return self._client
