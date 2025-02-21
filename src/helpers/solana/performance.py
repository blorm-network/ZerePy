from venv import logger
from typing import List, Optional
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from src.types import (
    NetworkPerformanceMetrics,
)
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore


async def fetch_performance_samples(
    async_client: AsyncClient, wallet: Keypair, sample_count: int = 1
) -> List[NetworkPerformanceMetrics]:
    """
    Fetch detailed performance metrics for a specified number of samples.

    Args:
        agent: An instance of SolanaAgent providing the RPC connection.
        sample_count: Number of performance samples to retrieve (default: 1).

    Returns:
        A list of NetworkPerformanceMetrics objects.

    Raises:
        ValueError: If performance samples are unavailable or invalid.
    """

    try:
        performance_samples = await async_client.get_recent_performance_samples(
            sample_count
        )

        if not performance_samples:
            raise ValueError("No performance samples available.")

        return [
            NetworkPerformanceMetrics(
                transactions_per_second=sample["num_transactions"]
                / sample["sample_period_secs"],
                total_transactions=sample["num_transactions"],
                sampling_period_seconds=sample["sample_period_secs"],
                current_slot=sample["slot"],
            )
            for sample in performance_samples
        ]

    except Exception as error:
        raise ValueError(
            f"Failed to fetch performance samples: {str(error)}"
        ) from error


class SolanaPerformanceTracker:
    """
    A utility class for tracking and analyzing Solana network performance metrics.
    """

    def __init__(self, async_client: AsyncClient, wallet: Keypair):
        self.async_client = async_client
        self.wallet = wallet
        self.metrics_history: List[NetworkPerformanceMetrics] = []

    def record_latest_metrics(self) -> NetworkPerformanceMetrics:
        """
        Fetch the latest performance metrics and add them to the history.

        Returns:
            The most recent NetworkPerformanceMetrics object.
        """
        latest_metrics = fetch_performance_samples(self.async_client, 1)
        self.metrics_history.append(latest_metrics[0])
        return latest_metrics[0]

    def calculate_average_tps(self) -> Optional[float]:
        """
        Calculate the average TPS from the recorded performance metrics.

        Returns:
            The average TPS as a float, or None if no metrics are recorded.
        """
        if not self.metrics_history:
            return None
        return sum(
            metric.transactions_per_second for metric in self.metrics_history
        ) / len(self.metrics_history)

    def find_maximum_tps(self) -> Optional[float]:
        """
        Find the maximum TPS from the recorded performance metrics.

        Returns:
            The maximum TPS as a float, or None if no metrics are recorded.
        """
        if not self.metrics_history:
            return None
        return max(metric.transactions_per_second for metric in self.metrics_history)

    def reset_metrics_history(self) -> None:
        """Clear all recorded performance metrics."""
        self.metrics_history.clear()

    async def fetch_current_tps(async_client: AsyncClient) -> float:
        """
        Fetch the current Transactions Per Second (TPS) on the Solana network.

        Args:
            agent: An instance of SolanaAgent providing the RPC connection.

        Returns:
            Current TPS as a float.

        Raises:
            ValueError: If performance samples are unavailable or invalid.
        """
        try:
            response = await async_client.get_recent_performance_samples(1)

            performance_samples = response.value
            # logger.debug("Performance Samples:", performance_samples)

            if not performance_samples:
                raise ValueError("No performance samples available.")

            sample = performance_samples[0]

            if (
                not all(
                    hasattr(sample, attr)
                    for attr in ["num_transactions", "sample_period_secs"]
                )
                or sample.num_transactions <= 0
                or sample.sample_period_secs <= 0
            ):
                raise ValueError("Invalid performance sample data.")

            return sample.num_transactions / sample.sample_period_secs

        except Exception as error:
            raise ValueError(f"Failed to fetch TPS: {str(error)}") from error
