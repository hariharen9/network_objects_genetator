import ipaddress
import json
import os
import random
import string
import subprocess
import sys
import time

# List of Kubernetes resource kinds used in NetSim
K8S_RESOURCE_KINDS = [
    "router", "clusternetwork", "publicaddressrange", "routingtable",
    "networkacl", "securitygroup", "network", "ipaddress", "reservedip",
    "virtualnetworkinterface", "sharemounttarget", "endpointgateway", "networkendpoint",
    "networkinterface", "virtualnic", "loadbalancer", "lbpool",
    "lblistener", "lbpoolmember",
    "flowlog"
]

creation_order = {
        "ClusterNetwork": "01",
        "Router": "01",
        "RoutingTable": "02",
        "SecurityGroup": "03",
        "NetworkACL": "04",
        "Network": "05",
        "ForeignNetwork": "05",
        "PublicAddressRange": "06",
        "ReservedIP": "07",
        "EndpointGateway": "08",
        "ShareMountTarget": "09",
        "VirtualNetworkInterface": "10",
        "VirtualNic": "11",
        "LoadBalancer": "12",
        "LBPool": "13",
        "LBListener": "14",
        "LBPoolMember": "15",
        "NetworkEndpoint": "16",
        "NetworkInterface": "17",
        "FlowLog": "20"
    }

def print_red(text, **kwargs):
    print("\033[91m" + str(text) + "\033[0m", **kwargs)

def print_green(text, **kwargs):
    print("\033[92m" + str(text) + "\033[0m", **kwargs)

def print_yellow(text, **kwargs):
    print("\033[93m" + str(text) + "\033[0m", **kwargs)

def get_octets(index):
    if index > 65000:
        print_yellow(f"Warning: Index {index} is larger than 65535 and will be wrapped around.")
        index = index % 65536
    octet3 = index // 256
    octet4 = index % 256
    return octet3, octet4

def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.stdout

def run_command_strip(command):
    outp = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    if outp.returncode != 0:
        print(f"{outp.stderr}")
    return outp.stdout.strip()

def apply(command, kind):
    print(f"Applying {kind}..")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    print(result.stdout)
    return result

def extract_metadata(yaml_template):
    namespace = yaml_template["metadata"]["namespace"]
    kind = yaml_template["kind"]
    idName = yaml_template["metadata"]["name"]
    return namespace, kind, idName

def kubectl_check(namespace, kind, name, yaml_str):
    if kind and namespace and name:
        check_command = f'kubectl get {kind.lower()} {name} -n {namespace} '
        sleep_time = 0.5 if kind.lower() in ['virtualnic'] else 0 #Giving VNIC creation some grace time to reflect
        time.sleep(sleep_time)
        try:
            result = subprocess.check_output(check_command, shell=True, stderr=subprocess.STDOUT)
            print(f"{result.decode('utf-8')}K8S Object Check : \033[92m" + "OK" + "\033[0m \n")
        except subprocess.CalledProcessError as e:
            error_message = e.output.decode('utf-8')
            print_red(f"Error occurred: {error_message}")

            # Write the errored Kind's yaml into a file for debugging
            with open(f'error_creating_{kind}_{name}.yaml', 'a') as error_file:
                error_file.write(yaml_str)
                error_file.close()
    else:
        print(f"Invalid Object, Cannot check right now.")

def generate_route_distinguisher(mz):
    # Generating random IPv4 address (32-bit) & Fixed only integers as MZ prefix cause I faced an issue where multiple routers had same RDs
    ipv4_address = "".join(str(random.randint(0, 255)) for i in range(4))
    prefix = mz
    mz_numeric = ''.join('0' if char.isalpha() else char for char in prefix)
    ipv4_address = "".join(str(random.randint(0, 255)) for i in range(4))
    route_distinguisher = f"{mz_numeric}:{ipv4_address}"

    return route_distinguisher

def generate_ip_address(ip_range):
    # Generates IP addresses in the given range
    network = ipaddress.ip_network(ip_range)
    ip_address = random.choice(list(network.hosts()))
    return str(ip_address)

def set_executable_permission(filename):
    os.chmod(filename, 0o755)

def time_taken(start_time, setCount):
    end_time = time.time()
    exec_time = end_time - start_time
    minute = False
    if exec_time > 60:
        exec_time = exec_time/60
        minute = True
    if minute:
        print_green(f"Total time taken to apply {setCount} Sets of resources is = \033[91m" + str(round(exec_time, 2)) + "\033[0m" + " Minutes")
    else:
        print_green(f"Total time taken to apply {setCount} Sets of resources is = \033[91m" + str(round(exec_time, 2)) + "\033[0m" + " Seconds")

def generate_serviceGatewayIP(routerIndex):
    octet3, octet4 = get_octets(routerIndex)
    serviceGatewayIP_address = f"192.21.{octet3}.{octet4}"
    serviceGatewayIP_range = f"192.21.{octet3}.0/24"
    return serviceGatewayIP_address, serviceGatewayIP_range

def generate_serviceGatewayStaticRoutes(routerIndex):
    octet2_1, octet3_1  = get_octets(routerIndex + 1)
    octet2_2, octet3_2  = get_octets(routerIndex + 2)
    serviceGatewayStaticRoutes_ips = [
        f"192.{octet2_1}.{octet3_1}.0/24",
        f"192.{octet2_2}.{octet3_2}.0/24"
    ]
    return serviceGatewayStaticRoutes_ips

def generate_addressPrefixes(routerIndex, count):
    # Each VPC needs a unique block of indices to avoid CIDR collision. It will use 'count' prefixes for local networks and 'count' for foreign networks.
    block_size_per_vpc = count * 2
    base_index = routerIndex * block_size_per_vpc
    
    local_prefixes = []
    for i in range(count):
        octet2, octet3 = get_octets(base_index + i)
        local_prefixes.append(f"192.{octet2}.{octet3}.0/24")

    foreign_prefixes = []
    for i in range(count):
        octet2, octet3 = get_octets(base_index + count + i)
        foreign_prefixes.append(f"192.{octet2}.{octet3}.0/24")

    router_address_prefixes = local_prefixes + foreign_prefixes

    return router_address_prefixes, local_prefixes, foreign_prefixes

def add_suffix_to_prefix(prefix, suffix_count):
    try:
        suffix_count = int(suffix_count)
    except (TypeError, ValueError):
        suffix_count = 5  # Fallback value
    
    prefix = str(prefix)
    return f"{prefix}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=suffix_count))}"

def get_compute_nodes(sn,en):
    specificnode = sn
    excludenode = en
    # Check if we already have cached results
    if not hasattr(get_compute_nodes, 'cached_nodes'):
        get_compute_nodes.cached_nodes = run_command("kubectl -n sim-ns get nodes --show-labels | grep compute | awk '{print $1}'").split()
        print_green(f"Compute Nodes: {[node.decode('utf-8') for node in get_compute_nodes.cached_nodes]}")
    
    # local_test_nodes = [b'region1-node-01', b'region1-node-02'] # Used for local testing
    # return local_test_nodes
    
    if specificnode:
        get_compute_nodes.cached_nodes = [node for node in get_compute_nodes.cached_nodes if node.decode('utf-8') in specificnode]
    if excludenode:
        get_compute_nodes.cached_nodes = [node for node in get_compute_nodes.cached_nodes if node.decode('utf-8') not in excludenode]
    
    # For real data, uncomment this:
    return get_compute_nodes.cached_nodes

def load_and_process_config(parser, config_path):
    """Loads arguments from a JSON config file, handling nested structures."""
    # Get a namespace with all the default values from the parser
    args = parser.parse_args([])

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Flatten the nested config and update the args namespace
    for section_name, section_data in config.items():
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                if hasattr(args, key):
                    setattr(args, key, value)

    # Ensure the action is set, as it's a required argument
    if 'run_settings' in config and 'action' in config['run_settings']:
        args.action = config['run_settings']['action']
    
    return args

def cpu_check(args):
    workers = 0
    mode = ""
    if args.fullyparallel is not None:
        workers = args.fullyparallel
        mode = "fully parallel"
    elif args.parallel is not None:
        workers = args.parallel
        mode = "parallel"
    else:
        # No parallel mode, so no check needed.
        return

    if workers > 50:
        if workers == os.cpu_count():
            print_yellow(f"Warning: You are attempting to use all available CPU cores ({workers}) for {mode} processing. This may lead to system instability or unresponsiveness.")
        elif workers < os.cpu_count():
            print_yellow(f"You are using {workers} workers, which is less than the available CPU cores ({os.cpu_count()}). This is generally safe, but monitor your system's performance.")
        else:
            print_yellow(f"Warning: A high number of {mode} workers ({workers}) can put significant strain on the Kubernetes API server. This is more than your current CPU count ({os.cpu_count()}). Proceed with caution.")
            try:
                confirm = input("Do you want to proceed? (y/n): ").lower()
                if confirm not in ['y', 'yes']:
                    print_yellow("Operation cancelled by user.")
                    sys.exit(1)
            except KeyboardInterrupt:
                print_yellow("\nOperation cancelled by user.")
                sys.exit(1)

def get_fnw_prefix():
    try:
        get_cm_command = "kubectl get cm sim-ns-globals -n sim-ns -o jsonpath='{.data.network_workspace}'"
        network_workspace_json = run_command_strip(get_cm_command)

        if not network_workspace_json:
            print("Could not retrieve 'network_workspace' from sim-ns-globals ConfigMap.")
            return None

        network_workspace_data = json.loads(network_workspace_json)
        multi-zone_zones = network_workspace_data.get("multi-zone")
        
        if not multi-zone_zones:
            print("The 'multi-zone' field in sim-ns-globals is empty or not found.")
            return None
        
        raw_fnw_prefix = multi-zone_zones[0]

        if raw_fnw_prefix.startswith("zone"):
            fnw_prefix = raw_fnw_prefix[5:] # Stripping "zone"
            print(f"Found foreign network prefix from MZR: {fnw_prefix}")
            return fnw_prefix
        else:
            print(f"Unable to decode the zone name '{raw_fnw_prefix}' from sim-ns-globals.")
            return None
        
    except Exception as e:
        print_red(f"An unexpected error occurred while fetching MZR info for FNW: {e}")
        return None
        
def get_rip_ip_address(rip_name, namespace, timeout=10, interval=1):
    print_yellow(f"Polling ReservedIP '{rip_name}' for its status.ipv4 address...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        command = f"kubectl get reservedip {rip_name} -n {namespace} -o json"
        result = run_command(command)
        if result:
            try:
                rip_json = json.loads(result)
                ipv4_address = rip_json.get("status", {}).get("ipv4")
                if ipv4_address:
                    print_green(f"Found IP: {ipv4_address}")
                    return ipv4_address
                else:
                    print_yellow(f"IP not yet available. Retrying in {interval} seconds...")
            except json.JSONDecodeError:
                print_red(f"Error decoding JSON for ReservedIP '{rip_name}'.")
        
        time.sleep(interval)

    print_red(f"Error: Timed out after {timeout} seconds waiting for ReservedIP '{rip_name}' to get an IP address.")
    return None
        
def checking_mode_for_epgw(args):
    is_batch_or_parallel = args.batchapply or args.parallel or args.fullyparallel
    if args.epgwcount > 0 and is_batch_or_parallel:
        print_green("To create EPGWs, please use the sequential '--apply' (-a) flag with '--epgw' (--endpointgateway), or generate and manually apply the ipv4 populated YAML files.")
        print_yellow("Skipping EPGW creation for this run.")
        args.epgwcount = 0  # Disabling EPGW creation
    return args

def checking_mode_for_nep_nif(args):
    is_batch_or_parallel = args.batchapply or args.parallel or args.fullyparallel
    if args.nep_nif and is_batch_or_parallel:
        print_green("To create NEP/NIF, please use the sequential '--apply' (-a) flag with '-nn' (--nep-nif), or generate and manually apply the UID populated YAML files.")
        print_yellow("Skipping NEP/NIF creation for this run.")
        args.nep_nif = False # Disabling NEP/NIF creation
    return args

def get_k8s_resource_uid(kind, name, namespace, timeout=10, interval=1):
    start_time = time.time()
    while time.time() - start_time < timeout:
        command = f"kubectl get {kind} {name} -n {namespace} -o jsonpath='{{.metadata.uid}}'"
        result = run_command_strip(command)
        if result:
            return result
        else:
            print_yellow(f"UID for {kind} '{name}' not yet available. Retrying in {interval} seconds...")
            time.sleep(interval)
    
    print_red(f"Error: Could not retrieve UID for {kind} '{name}' in namespace '{namespace}' after {timeout} seconds.")
    return None