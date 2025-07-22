import asyncio
from dataclasses import dataclass
import os
import re
import time
from typing import Dict, List, Optional, Tuple

# Import configuration
try:
    from config import CUSTOM_ENTRIES, DEFAULT_CONFIG, DYNAMIC_SERVICES, STATIC_SERVICES
except ImportError:
    # Fallback to built-in configuration if config.py is not available
    print("Warning: config.py not found, using built-in configuration")
    DYNAMIC_SERVICES = {}
    STATIC_SERVICES = {}
    CUSTOM_ENTRIES = {}
    DEFAULT_CONFIG = {
        "data_directory": "./data",
        "output_file": "hosts",
        "ping_attempts": 2,  # ping attempts
        "ping_timeout": 0.5,  # ping timeout (seconds)
        "ping_max_workers": 50,  # asynchronous concurrency limit
        "good_enough_threshold": 50.0,  # latency threshold (milliseconds)
        "max_workers": None,  # CPU cores (None for default)
    }


class Logger:
    """A utility class for stylized log output."""

    @staticmethod
    def header(title: str) -> None:
        """Prints a header with the given title."""
        print("\n" + "=" * 62)
        print(f"   {title}")
        print("=" * 62)

    @staticmethod
    def section(title: str) -> None:
        """Prints a section title."""
        print(f"\n📋 {title}")
        print("─" * (len(title) + 4))

    @staticmethod
    def service_start(name: str, total: int, current: int) -> None:
        """Prints a message when a service test starts."""
        print(f"  🔍 [{current:2d}/{total}] Testing {name}...")

    @staticmethod
    def service_result(
        name: str, ip: str, latency: float, total: int, current: int, status: str = "success"
    ) -> None:
        """Prints the result of a service test."""
        if status == "success" and ip:
            emoji = "✅"
            status_text = f"{ip} ({latency:.1f}ms)"
        elif status == "no_ip":
            emoji = "❌"
            status_text = "No available IP found"
        else:
            emoji = "⚠️"
            status_text = "Test failed"

        print(f"  {emoji} [{current:2d}/{total}] {name:<25} -> {status_text}")

    @staticmethod
    def progress(current: int, total: int, best_ip: str = "", best_time: float = 0, end: str = '\r') -> None:
        """Prints a progress bar (only for very slow operations)."""
        # Only show progress for large IP sets (>100) and when progress is meaningful
        if total < 100 or current % 20 != 0:
            return

        percent = (current / total) * 100
        filled = int(percent // 5)
        bar = "█" * filled + "░" * (20 - filled)

        best_info = ""
        if best_ip and best_time < float("inf"):
            best_info = f" | Best: {best_ip} ({best_time:.1f}ms)"

        print(f"    📊 Progress: [{bar}] {percent:5.1f}% ({current}/{total}){best_info}", end=end)

    @staticmethod
    def completion_summary(total_time: float) -> None:
        """Prints a summary upon completion."""
        print("\n" + "=" * 62)
        print(f"   Testing complete! Total time: {total_time:.1f} seconds")
        print("=" * 62)

    @staticmethod
    def file_generated(filename: str) -> None:
        """Prints a message when a file is generated."""
        print(f"\n📄 Hosts file generated: {filename}")

    @staticmethod
    def usage_instructions() -> None:
        """Prints usage instructions."""
        print("\n📖 Usage Instructions:")
        print("   1. View the contents of the generated hosts file")
        print("   2. Copy only the necessary entries to the system hosts file")
        print("   3. It is recommended to only replace problematic IP addresses")
        print("   4. Some services use global CDN, which may not require manual configuration")

    @staticmethod
    def error(message: str) -> None:
        """Prints an error message."""
        print(f"❌ Error: {message}")

    @staticmethod
    def warning(message: str) -> None:
        """Prints a warning message."""
        print(f"⚠️  Warning: {message}")


@dataclass
class ServiceConfig:
    """Configuration for a Microsoft service.

    Parameters:
    -----------
    name : str
        Readable name of the service
    ip_file_path : str
        Path to the file containing candidate IP addresses
    domains : List[str]
        List of domains for the service
    static_ip : Optional[str], default=None
        Static IP address (overrides automatic selection if provided)
    """

    name: str
    ip_file_path: str
    domains: List[str]
    static_ip: Optional[str] = None


class AsyncPingTester:
    """Asynchronous IP address network latency tester.

    This class tests network latency by asynchronously pinging IP addresses and selects the optimal IP based on response time.

    Parameters:
    -----------
    attempts : int, default=2
        Number of ping attempts for each IP address
    timeout : float, default=0.5
        Timeout for each ping attempt (seconds)
    semaphore_limit : int, default=50
        Concurrency limit semaphore
    good_enough_threshold : float, default=50.0
        Latency threshold (milliseconds) below which testing can stop early
    """

    def __init__(
        self,
        attempts: int = 2,
        timeout: float = 0.5,
        semaphore_limit: int = 50,
        good_enough_threshold: float = 50.0,
    ):
        self.attempts = attempts
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.good_enough_threshold = good_enough_threshold

    async def ping_ip(self, ip: str) -> float:
        """Asynchronously tests the latency of a single IP address.

        Parameters:
        -----------
        ip : str
            IP address to test

        Returns:
        --------
        float
            Average latency (milliseconds), returns float('inf') if unreachable
        """
        async with self.semaphore:  # Limit concurrency
            total_time = 0.0
            successful_pings = 0

            for _ in range(self.attempts):
                try:
                    # Asynchronous version of the system ping command
                    start_time = asyncio.get_event_loop().time()

                    process = await asyncio.create_subprocess_exec(
                        "ping",
                        "-c",
                        "1",
                        "-W",
                        str(int(self.timeout * 1000)),
                        ip,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=self.timeout + 0.1
                    )

                    if process.returncode == 0:
                        # Parse ping output to get time
                        output = stdout.decode()
                        # Look for latency time in the format time=xx.xx
                        time_match = re.search(r"time[=<](\d+\.?\d*)", output)
                        if time_match:
                            ping_time = float(time_match.group(1))
                            total_time += ping_time
                            successful_pings += 1
                        else:
                            # If parsing fails, use measured time
                            end_time = asyncio.get_event_loop().time()
                            measured_time = (end_time - start_time) * 1000
                            total_time += measured_time
                            successful_pings += 1

                except (asyncio.TimeoutError, OSError):
                    # Ping failed or timed out
                    continue

            if successful_pings == 0:
                return float("inf")

            return total_time / successful_pings

    async def find_best_ip(self, ip_file_path: str) -> Tuple[str, float]:
        """Asynchronously selects the IP address with the lowest latency from a file.

        Parameters:
        -----------
        ip_file_path : str
            Path to the file containing IP addresses (one IP per line)

        Returns:
        --------
        Tuple[str, float]
            Optimal IP address and its average latency (milliseconds)

        Exceptions:
        -------
        FileNotFoundError
            If the IP file does not exist
        """
        if not os.path.exists(ip_file_path):
            raise FileNotFoundError(f"IP file not found: {ip_file_path}")

        # Read all IP addresses
        ips = []
        with open(ip_file_path, "r", encoding="utf-8") as file:
            for line in file:
                ip = line.strip()
                if ip and not ip.startswith("#"):  # Skip empty lines and comments
                    ips.append(ip)

        if not ips:
            return "", float("inf")

        # For a large number of IPs, test the first 20% first, and stop if a good result is found
        if len(ips) > 50:
            sample_size = max(10, len(ips) // 5)  # Test at least 10, or 20% of the total
            sample_ips = ips[:sample_size]

            best_ip, best_time = await self._test_ip_batch_async(sample_ips)

            # If a good IP is found in the sample (below threshold), do not continue testing
            if best_time <= self.good_enough_threshold:
                return best_ip, best_time

            # Otherwise test the remaining IPs
            remaining_ips = ips[sample_size:]
            if remaining_ips:
                remaining_best_ip, remaining_best_time = await self._test_ip_batch_async(
                    remaining_ips, best_time
                )

                if remaining_best_time < best_time:
                    return remaining_best_ip, remaining_best_time

            return best_ip, best_time
        else:
            # Not many IPs, test all
            return await self._test_ip_batch_async(ips)

    async def _test_ip_batch_async(
        self, ips: List[str], current_best_time: float = float("inf")
    ) -> Tuple[str, float]:
        """Internal method to asynchronously test a batch of IP addresses.

        Parameters:
        -----------
        ips : List[str]
            List of IPs to test
        current_best_time : float
            Current best time, used for early termination

        Returns:
        --------
        Tuple[str, float]
            Optimal IP address and its average latency (milliseconds)
        """
        best_ip = ""
        best_time = current_best_time

        # Create all ping tasks
        tasks = []
        for ip in ips:
            task = asyncio.create_task(self.ping_ip(ip))
            tasks.append((task, ip))

        # Process in batches
        completed = 0
        batch_size = 20  # Process 20 per batch

        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i : i + batch_size]

            try:
                # Wait for the current batch to complete
                for task, ip in batch_tasks:
                    try:
                        avg_time = await task

                        if avg_time < best_time:
                            best_ip = ip
                            best_time = avg_time

                        completed += 1

                        # If a good enough IP is found, terminate early
                        if best_time <= self.good_enough_threshold:
                            # Cancel remaining tasks
                            for j in range(i + batch_size, len(tasks)):
                                remaining_task, _ = tasks[j]
                                if not remaining_task.done():
                                    remaining_task.cancel()
                            return best_ip, best_time

                    except Exception:
                        # Ignore single IP test errors
                        completed += 1
                        continue

            except Exception:
                # Ignore batch processing errors
                continue

        return best_ip, best_time


class ConfigurationManager:
    """Service configuration loading and validation manager.

    This class is responsible for loading service configurations from external files and converting them into internal ServiceConfig objects.

    Parameters:
    -----------
    data_dir : str, default='./data'
        Directory where IP address files are stored
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir

    def load_dynamic_services(self) -> Dict[str, ServiceConfig]:
        """Loads dynamic services from configuration.

        Returns:
        --------
        Dict[str, ServiceConfig]
            Dictionary of service keys to configurations
        """
        services = {}

        for service_key, config in DYNAMIC_SERVICES.items():
            ip_file_path = os.path.join(self.data_dir, config["ip_file"])
            services[service_key] = ServiceConfig(
                name=config["name"], ip_file_path=ip_file_path, domains=config["domains"]
            )

        return services

    def load_static_services(self) -> List[ServiceConfig]:
        """Loads static services from configuration.

        Returns:
        --------
        List[ServiceConfig]
            List of services with predefined static IPs
        """
        services = []

        for service_key, config in STATIC_SERVICES.items():
            services.append(
                ServiceConfig(
                    name=config["name"],
                    ip_file_path="",
                    domains=config["domains"],
                    static_ip=config["ip"],
                )
            )

        return services

    def get_custom_entries(self) -> Dict[str, Dict]:
        """Gets custom host entries from configuration.

        Returns:
        --------
        Dict[str, Dict]
            Dictionary of custom host entries
        """
        return CUSTOM_ENTRIES.copy()


class HostsFileGenerator:
    """hosts file content generator.

    This class is responsible for formatting and organizing hosts file entries by service type.

    Parameters:
    -----------
    output_file : str, default='hosts'
        Output file name for the hosts file
    """

    def __init__(self, output_file: str = "hosts"):
        self.output_file = output_file
        self._content = []

    def add_section(self, title: str, ip: str, domains: List[str]) -> None:
        """Adds a service section to the hosts file.

        Parameters:
        -----------
        title : str
            Section title (as a comment)
        ip : str
            IP address corresponding to the domain
        domains : List[str]
            List of domains to map to the IP
        """
        if not domains:  # Skip sections with no domains
            return

        self._content.append(f"# {title}")

        for domain in domains:
            self._content.append(f"{ip} {domain}")

        self._content.append("")  # Empty line for separation

    def add_custom_section(self, title: str, entries: List[str]) -> None:
        """Adds a custom section (formatted entries).

        Parameters:
        -----------
        title : str
            Section title
        entries : List[str]
            List of formatted host entries
        """
        if not entries:  # Skip empty custom sections
            return

        self._content.append(f"# {title}")
        self._content.extend(entries)
        self._content.append("")

    def write_file(self) -> None:
        """Writes the hosts content to a file.

        Exceptions:
        -------
        IOError
            If file writing fails
        """
        try:
            with open(self.output_file, "w", encoding="utf-8") as file:
                file.write("\n".join(self._content))
        except IOError as e:
            raise IOError(f"Failed to write hosts file: {e}")

    def get_content(self) -> str:
        """Gets the current hosts file content (string).

        Returns:
        --------
        str
            Complete hosts file content
        """
        return "\n".join(self._content)

    def clear(self) -> None:
        """Clears all content in the generator."""
        self._content.clear()


class MicrosoftHostsPicker:
    """Main flow controller for Microsoft Hosts Picker.

    This class is responsible for coordinating the complete process of IP testing, optimal IP selection, and hosts file generation.

    Parameters:
    -----------
    config : Dict, optional
        Configuration dictionary. Uses DEFAULT_CONFIG if None
    """

    def __init__(self, config: Optional[Dict] = None):
        if config is None:
            config = DEFAULT_CONFIG

        self.config = config
        # Use asynchronous ping tester
        self.ping_tester = AsyncPingTester(
            attempts=config.get("ping_attempts", 2),
            timeout=config.get("ping_timeout", 0.5),
            semaphore_limit=config.get("ping_max_workers", 50),
            good_enough_threshold=config.get("good_enough_threshold", 50.0),
        )
        self.config_manager = ConfigurationManager(data_dir=config.get("data_directory", "./data"))
        self.hosts_generator = HostsFileGenerator(output_file=config.get("output_file", "hosts"))

    async def test_services(self) -> Dict[str, Tuple[str, float]]:
        """Tests all dynamic services and selects the optimal IP.

        Uses sequential testing for cleaner, more readable output.

        Returns:
        --------
        Dict[str, Tuple[str, float]]
            Dictionary of service keys to (optimal IP, latency)
        """
        services = self.config_manager.load_dynamic_services()

        if not services:
            Logger.warning("No dynamic services configured for testing")
            return {}

        Logger.section(f"Testing {len(services)} Microsoft services")

        # Record start time
        start_time = time.time()

        # Filter valid services
        valid_services = []
        for service_key, config in services.items():
            if os.path.exists(config.ip_file_path):
                valid_services.append((service_key, config))
            else:
                Logger.warning(f"IP file does not exist: {config.name} -> {config.ip_file_path}")

        results = {}
        total_services = len(valid_services)

        # Test services sequentially for clean output
        for i, (service_key, config) in enumerate(valid_services, 1):
            Logger.service_start(config.name, total_services, i)
            
            try:
                ip, latency = await self.ping_tester.find_best_ip(config.ip_file_path)
                results[service_key] = (ip, latency)

                if ip:
                    Logger.service_result(
                        config.name, ip, latency, total_services, i, "success"
                    )
                else:
                    Logger.service_result(
                        config.name, "", 0, total_services, i, "no_ip"
                    )

            except Exception:
                Logger.service_result(
                    config.name, "", 0, total_services, i, "error"
                )
                results[service_key] = ("", float("inf"))

        # Calculate total time
        total_time = time.time() - start_time
        Logger.completion_summary(total_time)

        return results

        return results

    def generate_hosts_file(self, test_results: Dict[str, Tuple[str, float]]) -> None:
        """Generates the hosts file based on the optimal IPs.

        Parameters:
        -----------
        test_results : Dict[str, Tuple[str, float]]
            IP test results, containing the optimal IP for each service
        """
        # Clear any existing content
        self.hosts_generator.clear()

        # Add custom entries first
        custom_entries = self.config_manager.get_custom_entries()
        for entry_key, entry_config in custom_entries.items():
            self.hosts_generator.add_custom_section(entry_config["name"], entry_config["entries"])

        # Add static services
        static_services = self.config_manager.load_static_services()
        for static_service in static_services:
            if static_service.static_ip and static_service.domains:
                self.hosts_generator.add_section(
                    static_service.name, static_service.static_ip, static_service.domains
                )

        # Add tested dynamic services
        dynamic_services = self.config_manager.load_dynamic_services()
        for service_key, (best_ip, _) in test_results.items():
            if service_key in dynamic_services and best_ip:
                config = dynamic_services[service_key]
                if config.domains:  # Only add services with domains
                    self.hosts_generator.add_section(config.name, best_ip, config.domains)

    def validate_configuration(self) -> bool:
        """Validates the current configuration.

        Returns:
        --------
        bool
            True if the configuration is valid, False otherwise
        """
        data_dir = self.config.get("data_directory", "./data")

        if not os.path.exists(data_dir):
            Logger.error(f"Data directory does not exist: '{data_dir}'")
            return False

        # Check if at least some IP files exist
        dynamic_services = self.config_manager.load_dynamic_services()
        existing_files = 0

        for service_key, config in dynamic_services.items():
            if os.path.exists(config.ip_file_path):
                existing_files += 1
            else:
                Logger.warning(f"IP file does not exist: {config.name} -> {config.ip_file_path}")

        if existing_files == 0:
            Logger.error("No valid IP files found")
            return False

        print(f"✅ Configuration validated: {existing_files} services ready")
        return True

    async def run(self) -> None:
        """Executes the complete Microsoft Hosts Picker process.

        This method includes:
        1. Validating the configuration
        2. Testing the optimal IP for all Microsoft services
        3. Generating the hosts file
        4. Providing user feedback and usage instructions
        """
        Logger.header("Microsoft Hosts Picker")

        # Validate configuration
        if not self.validate_configuration():
            Logger.error("Configuration validation failed, please check the configuration")
            return

        # Test dynamic services
        test_results = await self.test_services()

        if not test_results:
            Logger.error("Testing of all services failed")
            return

        # Generate hosts file
        Logger.section("Generating Hosts File")
        self.generate_hosts_file(test_results)

        try:
            self.hosts_generator.write_file()
            Logger.file_generated(self.hosts_generator.output_file)
        except IOError as e:
            Logger.error(f"Failed to write hosts file: {e}")
            return

        # Provide completion feedback
        Logger.usage_instructions()

        input("\n🎯 Press Enter to exit...")


async def main():
    """Main entry point for the Microsoft Hosts Picker application."""
    try:
        # Load configuration
        config = DEFAULT_CONFIG.copy()

        # Create and run the picker
        picker = MicrosoftHostsPicker(config)
        await picker.run()

    except KeyboardInterrupt:
        Logger.warning("User cancelled operation")
    except Exception as e:
        Logger.error(f"An unexpected error occurred: {e}")
        print("Please check the configuration and try again")
        input("Press Enter to exit...")


def sync_main():
    """Synchronous entry point, starts the asynchronous main function."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
