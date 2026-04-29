"""Tests for error handling and edge cases."""

from unittest.mock import MagicMock, patch

import pytest

from ready_redis import ReadyRedis
from ready_redis.ready_redis import ColabRedis, is_colab_environment


class TestColabEnvironmentDetection:
    """Tests for Google Colab environment detection."""
    
    def test_is_colab_environment_with_module(self):
        """Test when google.colab module exists."""
        mock_colab = MagicMock()
        mock_google = MagicMock()
        mock_google.colab = mock_colab
        
        with patch.dict("sys.modules", {"google": mock_google, "google.colab": mock_colab}):
            assert is_colab_environment() is True
    
    def test_is_colab_environment_without_module(self):
        """Test when google.colab module doesn't exist."""
        assert is_colab_environment() is False


class TestColabRedis:
    """Tests for ColabRedis class."""
    
    def test_colab_redis_initialization(self):
        """Test ColabRedis initialization."""
        colab = ColabRedis(port=6379, redis_args="--maxmemory 100mb")
        assert colab.port == 6379
        assert colab.redis_args == "--maxmemory 100mb"
        assert colab.process is None
    
    def test_colab_redis_stop_without_process(self):
        """Test stopping ColabRedis when no process exists."""
        colab = ColabRedis(port=6379, redis_args="")
        colab.stop()  # Should not raise
    
    def test_colab_redis_stop_with_process(self):
        """Test stopping ColabRedis with active process."""
        colab = ColabRedis(port=6379, redis_args="")
        mock_process = MagicMock()
        colab.process = mock_process
        colab.stop()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
    
    @patch("ready_redis.ready_redis.requests.get")
    def test_colab_redis_download_failure(self, mock_requests_get):
        """Test ColabRedis when download fails."""
        mock_requests_get.side_effect = Exception("Network error")
        
        colab = ColabRedis(port=6379, redis_args="")
        with pytest.raises(Exception, match="Network error"):
            colab.start()


class TestReadyRedisErrorHandling:
    """Tests for ReadyRedis error handling."""
    
    @patch("ready_redis.ready_redis.is_colab_environment")
    @patch("ready_redis.ready_redis.ColabRedis")
    def test_colab_start_failure(self, mock_colab_class, mock_is_colab):
        """Test when Colab Redis fails to start."""
        mock_is_colab.return_value = True
        mock_colab_instance = MagicMock()
        mock_colab_instance.start.side_effect = Exception("Start failed")
        mock_colab_class.return_value = mock_colab_instance
        
        with pytest.raises(Exception, match="Start failed"):
            ReadyRedis.get(redis_container_name="test-colab-fail", port=6500)
    
    @patch("ready_redis.ready_redis.importlib.resources.files")
    def test_docker_compose_not_found(self, mock_files):
        """Test when docker-compose.yml is not found."""
        mock_compose_path = MagicMock()
        mock_compose_path.is_file.return_value = False
        mock_files.return_value.__truediv__.return_value = mock_compose_path
        
        with pytest.raises(FileNotFoundError, match="docker-compose.yml not found"):
            ReadyRedis.get(redis_container_name="test-no-compose", port=6501)
    
    def test_shutdown_all_with_multiple_instances(self):
        """Test shutdown_all with multiple instances."""
        # Create instances
        r1 = ReadyRedis.get(redis_container_name="test-shutdown-1", port=6502)
        r2 = ReadyRedis.get(redis_container_name="test-shutdown-2", port=6503)
        
        # Mock cleanup to avoid actual Docker operations
        r1.cleanup = MagicMock()
        r2.cleanup = MagicMock()
        
        # Shutdown all
        ReadyRedis.shutdown_all()
        
        # Verify cleanup was called
        r1.cleanup.assert_called_once()
        r2.cleanup.assert_called_once()
        assert len(ReadyRedis._instances) == 0
    
    def test_cleanup_already_cleaned(self):
        """Test cleanup when already cleaned."""
        instance = ReadyRedis.get(redis_container_name="test-double-clean", port=6504)
        instance.cleanup()
        assert instance._cleaned_up is True
        
        # Mock compose to verify it's not called
        mock_compose = MagicMock()
        instance._compose = mock_compose
        
        # Second cleanup should return early
        instance.cleanup()
        mock_compose.stop.assert_not_called()
    
    def test_del_method_calls_cleanup(self):
        """Test __del__ method calls cleanup."""
        instance = ReadyRedis.get(redis_container_name="test-del", port=6505)
        mock_cleanup = MagicMock()
        instance.cleanup = mock_cleanup
        
        instance.__del__()
        mock_cleanup.assert_called_once()
    
    def test_container_name_property(self):
        """Test container_name property."""
        instance = ReadyRedis.get(redis_container_name="test-name-prop", port=6506)
        assert instance.container_name == "test-name-prop"
        instance.cleanup()
    
    def test_client_property(self):
        """Test client property returns Redis client."""
        instance = ReadyRedis.get(redis_container_name="test-client", port=6507)
        assert instance.client == instance._client
        assert instance.client.ping()
        instance.cleanup()
    
    @patch("ready_redis.ready_redis.sys.meta_path", None)
    def test_cleanup_with_no_meta_path(self):
        """Test cleanup when sys.meta_path is None."""
        instance = ReadyRedis.get(redis_container_name="test-no-meta", port=6508)
        instance._compose = MagicMock()
        instance.cleanup()
        assert instance._cleaned_up is True
    
    @patch("ready_redis.ready_redis.is_colab_environment")
    def test_cleanup_in_colab_environment(self, mock_is_colab):
        """Test cleanup in Colab environment."""
        mock_is_colab.return_value = True
        
        with patch("ready_redis.ready_redis.ColabRedis") as mock_colab_class:
            mock_colab_instance = MagicMock()
            mock_colab_class.return_value = mock_colab_instance
            
            with patch("ready_redis.ready_redis.redis.Redis"):
                instance = ReadyRedis.get(redis_container_name="test-colab-cleanup", port=6509)
                instance.cleanup()
                
                mock_colab_instance.stop.assert_called_once()
                assert instance._cleaned_up is True