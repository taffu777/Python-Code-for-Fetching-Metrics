import oci
import time
import psutil
from prometheus_client import start_http_server, Gauge

# Define OCI configuration variables
config = {
    "user": "user_id",
    "fingerprint": "finegrprint",
    "key_file": "path of pem.key",
    "tenancy": "tenancy_id",
    "region": "us-ashburn-1"
}

# Initialize the OCI clients
oci.config.validate_config(config)
monitoring_client = oci.monitoring.MonitoringClient(config)
load_balancer_client = oci.load_balancer.LoadBalancerClient(config)

# Define Prometheus metrics
cpu_utilization_gauge = Gauge('oci_instance_cpu_utilization', 'CPU Utilization of OCI instance', ['instance_id'])
memory_utilization_gauge = Gauge('oci_instance_memory_utilization', 'Memory Utilization of OCI instance', ['instance_id'])
memory_usage_gauge = Gauge('instance_memory_usage', 'Memory Usage of the instance', ['instance_id'])
disk_usage_gauge = Gauge('instance_disk_usage', 'Disk Usage of the instance', ['instance_id'])
network_in_gauge = Gauge('instance_network_in', 'Network Inbound Traffic of the instance', ['instance_id'])
network_out_gauge = Gauge('instance_network_out', 'Network Outbound Traffic of the instance', ['instance_id'])
lb_health_gauge = Gauge('oci_load_balancer_health', 'Health status of OCI Load Balancer', ['load_balancer_id'])
db_cpu_utilization_gauge = Gauge('oci_db_cpu_utilization', 'CPU Utilization of OCI Database', ['db_id'])
db_memory_utilization_gauge = Gauge('oci_db_memory_utilization', 'Memory Utilization of OCI Database', ['db_id'])
backend_set_health_gauge = Gauge('oci_backend_set_health', 'Health status of OCI Load Balancer Backend Set', ['load_balancer_id', 'backend_set_name'])

# List of instances, load balancers, and databases
instances = [
    {
        "instance_id": "instace_id",
        "load_balancer_id": "lb_id"
    },
    {
        "instance_id": "instnace_id",
        "load_balancer_id": "lb_id"
    },
    {
        "instance_id": "instance_id",
        "load_balancer_id": "lb_id"
    },
    {
        "instance_id": "instnace_id",
        "load_balancer_id": "lb_id"

    }
]

databases = [
    {
        "db_id": "database_id"
    }
]

# Function to fetch CPU utilization
def fetch_cpu_utilization(instance_id):
    try:
        response = monitoring_client.summarize_metrics_data(
            compartment_id=config['tenancy'],
            summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
                namespace="oci_computeagent",
                query=f'''CpuUtilization[1m]{{resourceId="{instance_id}"}}.max()'''
            )
        )

        if response.data:
            cpu_utilization = response.data[0].aggregated_datapoints[-1].value
            print(f"CPU Utilization for {instance_id}: {cpu_utilization}")
            cpu_utilization_gauge.labels(instance_id=instance_id).set(cpu_utilization)
        else:
            print(f"No CPU utilization data found for {instance_id}")
    except Exception as e:
        print(f"Error fetching CPU utilization for {instance_id}: {e}")

# Function to fetch Memory utilization
def fetch_memory_utilization(instance_id):
    try:
        response = monitoring_client.summarize_metrics_data(
            compartment_id=config['tenancy'],
            summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
                namespace="oci_computeagent",
                query=f'''MemoryUtilization[1m]{{resourceId="{instance_id}"}}.max()'''
            )
        )
        if response.data:
            memory_utilization = response.data[0].aggregated_datapoints[-1].value
            print(f"Memory Utilization for {instance_id}: {memory_utilization}")
            memory_utilization_gauge.labels(instance_id=instance_id).set(memory_utilization)
        elif len(response.data) == 0:
            print("Server Is In Stopped Condition")
        else:
            print("No Memory utilization data found")
    except Exception as e:
        print(f"Error fetching Memory utilization: {e}")

# Function to fetch load balancer status
def fetch_load_balancer_status(load_balancer_id):
    try:
        load_balancer = load_balancer_client.get_load_balancer(load_balancer_id).data
        load_balancer_status = load_balancer.lifecycle_state
        # Map the load balancer status to a numeric value
        status_mapping = {
            'CREATING': 1,
            'ACTIVE': 2,
            'UPDATING': 3,
            'DELETING': 4,
            'DELETED': 5,
            'FAILED': 6
        }
        lb_status_value = status_mapping.get(load_balancer_status, 0)
        print(f"Load Balancer Status for {load_balancer_id}: {lb_status_value}")
        lb_health_gauge.labels(load_balancer_id=load_balancer_id).set(lb_status_value)
    except Exception as e:
        print(f"Error fetching load balancer status for {load_balancer_id}: {e}")

# Function to fetch backend set health status
def fetch_backend_set_health_status(load_balancer_id):
    try:
        backend_sets = load_balancer_client.list_backend_sets(load_balancer_id).data
        for backend_set in backend_sets:
            backend_set_name = backend_set.name
            backend_set_health = load_balancer_client.get_backend_set_health(load_balancer_id, backend_set_name).data.status
            # Map the backend set health status to a numeric value
            health_mapping = {
                'OK': 1,
                'WARNING': 2,
                'CRITICAL': 3,
                'UNKNOWN': 4
            }
            backend_set_health_value = health_mapping.get(backend_set_health, 0)
            print(f"Backend Set Health Status for {backend_set_name} in {load_balancer_id}: {backend_set_health_value}")
            backend_set_health_gauge.labels(load_balancer_id=load_balancer_id, backend_set_name=backend_set_name).set(backend_set_health_value)
    except Exception as e:
        print(f"Error fetching backend set health status for {load_balancer_id}: {e}")

# Function to fetch memory usage
def fetch_memory_usage(instance_id):
    try:
        memory_info = psutil.virtual_memory()
        memory_usage_gauge.labels(instance_id=instance_id).set(memory_info.percent)
    except Exception as e:
        print(f"Error fetching memory usage for {instance_id}: {e}")

# Function to fetch disk usage
def fetch_disk_usage(instance_id):
    try:
        disk_info = psutil.disk_usage('/')
        disk_usage_gauge.labels(instance_id=instance_id).set(disk_info.percent)
    except Exception as e:
        print(f"Error fetching disk usage for {instance_id}: {e}")

# Function to fetch network I/O
def fetch_network_io(instance_id):
    try:
        net_io = psutil.net_io_counters()
        network_in_gauge.labels(instance_id=instance_id).set(net_io.bytes_recv)
        network_out_gauge.labels(instance_id=instance_id).set(net_io.bytes_sent)
    except Exception as e:
        print(f"Error fetching network I/O for {instance_id}: {e}")

# Function to fetch database CPU utilization
def fetch_db_cpu_utilization(db_id):
    try:
        response = monitoring_client.summarize_metrics_data(
            compartment_id=config['tenancy'],
            summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
                namespace="oci_database",
                query=f'CpuUtilization[1m]{{resourceId_database="{db_id}"}}.max()'
            )
        )
        if response.data:
            db_cpu_utilization = response.data[0].aggregated_datapoints[-1].value
            print(f"Database CPU Utilization for {db_id}: {db_cpu_utilization}")
            db_cpu_utilization_gauge.labels(db_id=db_id).set(db_cpu_utilization)
        else:
            print(f"No Database CPU utilization data found for {db_id}")
    except Exception as e:
        print(f"Error fetching Database CPU utilization for {db_id}: {e}")

# Function to fetch database Memory utilization
def fetch_db_memory_utilization(db_id):
    try:
        response = monitoring_client.summarize_metrics_data(
            compartment_id=config['tenancy'],
            summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
                namespace="oci_database",
                query=f'StorageUtilization[60m]{{resourceId_database="{db_id}"}}.max()'
            )
        )
        if response.data:
            db_memory_utilization = response.data[0].aggregated_datapoints[-1].value
            print(f"Database Memory Utilization for {db_id}: {db_memory_utilization}")
            db_memory_utilization_gauge.labels(db_id=db_id).set(db_memory_utilization)
        else:
            print(f"No Database Memory utilization data found for {db_id}")
    except Exception as e:
        print(f"Error fetching Database Memory utilization for {db_id}: {e}")

if __name__ == '__main__':
    # Start Prometheus metrics server
    start_http_server(port_no)

    while True:
        for instance in instances:
            fetch_cpu_utilization(instance["instance_id"])
            fetch_memory_utilization(instance["instance_id"])
            fetch_memory_usage(instance["instance_id"])
            fetch_disk_usage(instance["instance_id"])
            fetch_network_io(instance["instance_id"])
            fetch_load_balancer_status(instance["load_balancer_id"])
            fetch_backend_set_health_status(instance["load_balancer_id"])

        for db in databases:
            fetch_db_cpu_utilization(db["db_id"])
            fetch_db_memory_utilization(db["db_id"])

        time.sleep(10)

