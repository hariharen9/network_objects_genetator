# Network Resource Simulator ( NetSim )

A feature-rich command-line utility for simulating and managing network objects within a Kubernetes environment. Designed for rapid testing and development, this tool provides a comprehensive suite of commands to create, delete, and manipulate a wide array of network resources.

---

## Key Features

- **Comprehensive Resource Management**: Create and delete a wide range of network resources, including Routers, Security Groups, Networks, VNICs, and Load Balancers. This allows for the creation of complex network topologies for thorough testing.

  <details>
  <summary>Detailed List of Network Resources</summary>

  The Network Resource Simulator can create a wide range of Kubernetes-managed network resources:

  1.  **Core VPC & Networking Resources**:
      *   **Routers**: The central component for a Virtual Private Cloud (VPC).
      *   **Routing Tables**: Defines how traffic is routed within the network, including:
          *   Standard Routing Tables
          *   Ingress Routing Tables
      *   **Security Groups**: Controls inbound and outbound network traffic to virtual network interfaces.
      *   **NACLs (Network ACLs)**: Network Access Control Lists, providing filtering of network traffic.
      *   **Networks**: Represents subnets or segments within a VPC.
      *   **VNICs (VirtualNICs)**: Virtual network adapters attached to compute instances.
      *   **Foreign Networks**: Networks defined in other zones, often for cross-VPC communication.
      *   **Reserved IPs**: IP addresses reserved for specific resources, often associated with VNIs.
      *   **Endpoint Gateways (EPGW)**: Provides private access to the VPC.

  2.  **Load Balancer Resources**:
      *   **Load Balancers**: Distributes incoming network traffic across multiple VNIC instances.
      *   **LB Pools**: Collections of backend VNIC members that receive traffic from the load balancer.
      *   **LB Listeners**: Defines the protocol and port where the load balancer listens for incoming requests.
      *   **LB Pool Members**: Individual VNICs within an LB Pool.

  3.  **Virtual Network Interface (VNI) Related Resources**:
      These are used for advanced VNI configurations (like SMT, CVSI, XACC, or base VNI types).
      *   **Share Mount Targets (SMTs)**: Used for FaaS (File as a Service) for VNIs.
      *   **Virtual Network Interfaces (VNIs)**: A higher-level abstraction representing a virtual network attachment point, often linked to VNICs or SMTs.

  4.  **Other Specialized Resources**:
      *   **Cluster VSI (ClusterNetwork)**: A specialized network resource used instead of a Router for H100 GPU environments.
      *   **Public Address Ranges**: Defines blocks of public IP addresses.
  </details>
- **Advanced VNI Scenarios**: Supports various Virtual Network Interface (VNI) configurations, including `base` (VNI and VNIC in the same namespace), `smt` (Share Mount Target for FaaS), `cvsi` (ClusterVSI for H100), and `xacc` (Cross-Account). This enables testing of advanced networking features.
- **Targeted Operations**: Precisely control resource placement with node-specific targeting (`-sn`) and exclusion (`-en`) for VNICs. This is crucial for testing node-specific network configurations and features.
- **Debugging and Introspection**: A rich set of tools for debugging, including log retrieval (`getlogs`), cache inspection (`getcache`), real-time metrics (`getmetrics`), pod status monitoring (`watch`), and detailed resource status checks (`stat`, `describe`). This provides deep visibility into the state of the system.
- **Flexible Deployment**: Generate YAML files for review (`-a`) or apply them directly to the cluster. The batch-apply (`-ba`), parallel-apply (`-pa`) and fully-parallel apply (`-fp`) options provide drastic speed-ups for creating a large number of resources.
- **Image Management**: Easily view pod information (`getinfo`), update manager pod images to a new tag or revert to a previous version (`changeImage`), streamlining the process of testing new builds.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.x**
- A working Kubernetes environment with `kubectl` configured.

### Installation

You can set up the Network Resource Simulator in two ways:

#### **Option 1: Automated Deployment (Recommended)**

The provided deployment script creates a clean directory, copies all necessary files, and sets the correct permissions.

```bash
# Run the deployment script
./deploy_NRS.sh
```

**Note**:
```bash
# If you modify the source files (e.g., netsim.py, resourceGen.py), you need to regenerate the 'deploy_NRS.sh' script to include these changes. 
# To do this, run the 'update_deploy_NRS.sh' script from the source directory:
./update_deploy_NRS.sh
```

#### **Option 2: Manual Setup**

1.  Ensure the following files are in the same directory:
    - `netsim.py`
    - `resourceGen.py`
    - `cachetime.py`
    - `manipulation.py`
    - `pods.py`
    - `utils.py`
    - `template.json`
    - `config.json`
2.  Make the main script executable:
    ```bash
    chmod +x netsim.py
    ```

---

## 🛠️ Usage

### Command Structure

The script follows a simple `action` and `flags` structure.

```bash
./netsim.py <action> [arguments] [flags]
```

### Actions Overview

| Action | Short Form | Description |
| :--- | :--- | :--- |
| `create` | `c` | Create network resources like Routers, SGs, Networks, etc. |
| `delete` | `d` | Delete network resources from the specified namespace. |
| `get` | `g` | Get a summary of created resources in a namespace. |
| `describe` | `des` | Provide a detailed `kubectl describe` output for a resource. |
| `getstatus` | `gs` | Check the status of created VNICs and their underlying interfaces. |
| `stat` | | Get the raw `.status` block of a specific resource by kind or name. |
| `restart` | `r` | Restart one or all manager pods. |
| `getlogs` | `gl` | Fetch logs from manager pods. |
| `getcache` | `gc` | Restart all managers and retrieve cache synchronization info. |
| `manipulate` | `m` | Continuously update, and delete resources to simulate a live environment. |
| `cvsistress` | `cst` | Perform a stress test on CVSI resources. |
| `getinfo` | `gi` | Display the current information and image tags for manager pods. |
| `changeimage`| `ci` | Update manager pods to a new image tag or revert to a backup. |
| `getmetrics` | `gm` | Fetch and display metrics from manager pods. |
| `watch` | `w` | Continuously monitor the status of manager pods. |
| `leaks` | `lk` | Detects leaked net-core objects. |
| `removefinal`| `rf` | Force-deletes objects stuck in a 'Terminating' state. |

### In-Depth Action Descriptions

#### `create` / `c`
The core function for creating network resources. It can be used to create:
-   **VPC Components**: Routers, Routing Tables (including Ingress Routing Tables), Security Groups, NACLs, Networks, VNICs, Endpoint Gateways, and Foreign Networks.
-   **Load Balancer Components**: Load Balancers, LB Pools, LB Listeners, and LB Pool Members.
-   **VNI (Virtual Network Interface) Components**: Reserved IPs, Share Mount Targets (SMTs), and Virtual Network Interfaces (VNIs).
-   **Specialized Resources**: ClusterNetwork (for ClusterVSI scenarios) and Public Address Ranges.

It supports creating `n` VPCs with a single command. Various configurations are available:
-   **Base VNI**: With the `-vni` flag, it creates a VNI and a VNIC in the same namespace.
-   **VNI Phase 1 FaaS**: With `-vni smt`, it creates RIP, SMT, and VNI resources.
-   **ClusterVSI**: With `-vni cvsi`, it creates a `ClusterNetwork` instead of a `Router`.
-   **Cross-Account VNI**: With `-vni xacc`, it creates a VNI in a remote namespace linked to a local VNIC.
-   **Public Address Range**: With the `-parc <count>` flag.
- **Deployment Methods**: Use `-a` (apply), `-ba` (batch-apply), `-pa` (parallel-apply), or `-fp` (fully-parallel). These methods are mutually exclusive.
- **Endpoint Gateway (EPGW) Note**: Creating EPGWs (`--epgw`) requires the sequential `--apply` (`-a`) mode because the script must wait to retrieve the IP address from a `ReservedIP` before it can create the gateway.

#### `delete` / `d`
Deletes resources from a specified namespace.
- By default, it interactively asks for confirmation.
- Use `-f` or `--force` to delete without confirmation.
- Use `-y` or `--yes` to assume "yes" to all prompts, which is useful for non-interactive sessions.
- Use `-i` or `--interactive` for a menu-driven deletion process.
- Use `-dff` or `--deletefromfile` to delete resources listed in `applied_resources.txt`.

#### `get` / `describe` / `stat`
These commands help you inspect resources:
- `get`: Provides a quick summary of all resource kinds and their counts in a namespace.
- `describe <resource_type|resource_name>`: A wrapper for `kubectl describe`. Shows a human-readable summary, status, and events.
- `stat <resource_type|resource_name>`: Dumps the raw `status:` block from a resource's YAML. Ideal for checking specific status conditions.
- `getstatus`: A specific check for the status of created VNICs.

#### `restart` / `r`, `getlogs` / `gl`, `getcache` / `gc`
These actions are for interacting with the manager pods.
- `restart`: Restarts one or all manager pods.
- `getlogs`: Fetches logs, useful for debugging.
- `getcache`: A full restart cycle of all managers to get detailed cache synchronization information.

#### `manipulate` / `m` & `cvsistress` / `cst`
- `manipulate`: Simulates a production environment by randomly updating, and deleting resources.
- `cvsistress`: A focused stress test that repeatedly creates and deletes VNICs for CVSI.

#### `getinfo` / `gi` & `changeimage` / `ci`
- `getinfo`: Displays the current image tags of the manager pods.
- `changeimage`: Updates the manager pods to a new image tag (`--tag`) or reverts to the previous one (`--revert`).

#### `getmetrics` / `gm` & `watch` / `w`
- `getmetrics`: Fetches and displays Prometheus metrics from a selected manager pod. You can also provide an optional pattern to `grep` the output.
- `watch`: Provides a real-time, continuously updated view of the manager pods' status, similar to `watch kubectl get pods`.

#### `leaks` / `lk` & `removefinal` / `rf`
These commands are for advanced cluster cleanup and debugging.
- `leaks`: Runs the `./scripts/get_leaks.sh` script to find and report orphaned or leaked objects in the cluster.
- `removefinal <resource_type> <resource_name>`: **This is a destructive operation.** It forcefully removes the finalizers from a Kubernetes resource that is stuck in the 'Terminating' state. This allows the Kubernetes garbage collector to delete the object. Use with caution as it can lead to orphaned resources on the net-core-side if the controller did not clean them up properly.

### Flags

*Note: The apply methods (`-a`, `-ba`, `-pa`, `-fp`) are mutually exclusive.*

| Flag | Long Form | Description |
| :--- | :--- | :--- |
| `-e` | `--environment` | Target environment (`region-1` or `region-2`). Default: `region-1`. |
| `-ns`| `--namespace` | The Kubernetes namespace to use. Default: `sim-resources`. |
| `-n` | `--num` | Number of VPCs (Routers) to create. Default: `1`. |
| `-nc`| `--networkcount`| Number of networks to create per VPC. Default: `1`. |
| `-ec`| `--endpointcount`| Number of endpoints(VNICs) to create per node. Default: `1`. |
| `-ripc`| `--reservedipcount`| Number of Reserved IPs to create. Requires `-vni`. Default: `1`. |
| `-lb`| `--loadbalancer` | Include load balancers in the resource creation. |
| `-epgw`| `--endpointgateway` | Number of Endpoint Gateways to create. **Requires sequential apply (`-a`)**. |
| `-sy`| `--saveyaml` | Save the generated Kubernetes YAML files for debugging. |
| `-a` | `--apply` | Generate YAML files and apply them sequentially. |
| `-ba`| `--batch-apply` | Create and apply resources in efficient batches. |
| `-pa`| `--parallel-apply`| Create and apply resources with parallel application (sequential generation). |
| `-fp`| `--fully-parallel`| Create resources with fully parallel generation and application for maximum speed. |
| `-dff`| `--deletefromfile`| Delete resources listed in `applied_resources.txt`. |
| `-i` | `--interactive` | Enable interactive mode for deleting resources. |
| `-f` | `--force` | Force delete resources without confirmation. |
| `-y` | `--yes` | Assume 'yes' to all confirmation prompts (for non-interactive deletion). |
| `-cn`| `--containername` | Specify the container name for `restart` or `getlogs`. Default: `core-manager`. |
| `-sn`| `--specificnode` | Create VNICs on one or more specific nodes. |
| `-en`| `--excludenode` | Exclude one or more nodes from VNIC creation. |
| `-parc`| `--publicaddressrangecount`| Number of public address ranges to create. Default: `0`. |
| `-vni`| `--vnitype` | VNI type (`smt`, `cvsi`, `xacc`, `base`). |
| `-xacc-ns`|`--xacc-namespace`| Namespace for the cross-account VNI. Default: `xacc-ns`. |
| | `--tag` | The new image tag for the `changeImage` action. |
| | `--revert` | Revert to the previous image for the `changeImage` action. |
| | `--only` | Restricts the `changeimage` action to a specific manager deployment (`core-manager`, `net-manager`, `edge-manager`, or `clean-manager`). |

---

## ⚙️ Advanced Workflows and Examples

### 1. Basic VPC Creation

Create a simple VPC with default resources, verify its creation, and then clean up.

```bash
# Create a single VPC and generate the YAML files and helper scripts
./netsim.py create 

# Create a single VPC and apply the resources directly
./netsim.py create -a

# Get a summary of the created resources
./netsim.py get

# Check the status of the VNICs
./netsim.py getstatus

# Get the raw status block of a specific router
./netsim.py stat router <router-name>

# Delete all resources in the namespace when finished
./netsim.py delete -y
```

### 2. Creating Multiple VPCs with High Performance

Generate and apply multiple VPCs at high speed using either batch or parallel methods (note: keep `-n` below ~65k VPCs).

**Using Batch Apply (`-ba`)**
```bash
# Create 5 VPCs with load balancers using batch-apply
./netsim.py create -ba -n 5 -lb
```

**Using Parallel Apply (`-pa`)**
```bash
# Create 20 VPCs with a specific number of workers (e.g., 16)
./netsim.py create -pa 16 -n 20 -lb
```

**Using Fully Parallel Apply (`-fp`)**
```bash
# Create 100 VPCs with a specific number of workers (e.g., 16), Or can be used with the default number of workers ( number of available , just give -fp)
./netsim.py create -fp 16 -n 100
```

### 3. VNI Type Scenarios

This tool supports several VNI configurations for advanced testing.

```bash
# Create resources for a Base, same-namespace VNI
./netsim.py create -a --vnitype

# Create resources for a ShareMountTarget (SMT) VNI
./netsim.py create -a --vnitype smt

# Create resources for a ClusterVSI (CVSI) VNI
./netsim.py create -a --vnitype cvsi

# Create resources for a Cross-Account (XACC) VNI
./netsim.py create -a --vnitype xacc --xacc-namespace my-other-ns
```

### 4. Debugging and Introspection

Investigate the state of the system by fetching logs, monitoring pods, and describing resources.

```bash
# Get the image tags of all running manager pods
./netsim.py getinfo

# Watch the status of the manager pods in real-time
./netsim.py w

# Restart the core-manager pod
./netsim.py restart -cn core-manager

# Fetch logs from the core-manager pod
./netsim.py getlogs -cn core-manager

# Fetch metrics from a manager pod and filter for a specific pattern
./netsim.py gm go_goroutines

# Get detailed information about all security groups
./netsim.py describe securitygroup
```

### 5. Creating a VPC with an Endpoint Gateway

Create a VPC that includes an Endpoint Gateway **Note: The sequential apply (`-a`) flag is required for EPGW creation.**

```bash
# Create a single VPC and include one EPGW
./netsim.py create -a --epgw

# Create a single VPC with three EPGWs
./netsim.py create -a --epgw 3
```

### 6. Updating Manager Images

Update the `core-manager` and `net-manager` to a new image tag.

```bash
# Apply a new image tag to the deployments
./netsim.py changeimage --tag new-feature-tag-123

# If something goes wrong, revert to the previous image
./netsim.py changeimage --revert
```

---

## Additional Notes

- **Stateful Creation:** The `create` command is stateful. It tracks the last used VPC index in a hidden file (`.nrs_state_file.txt`) to prevent IP address conflicts on subsequent runs. To reset the counter, manually delete this file after ensuring the namespace is clean.

- **Configuration File:** For convenience, you can use a `config.json` file to specify arguments. If this file is present, the script will prompt you to use it. This avoids the need for long command-line flags. The structure mirrors the script's arguments:
  ```json
  {
    "description": "A complete configuration template. Modify values as needed.",
    "run_settings": {
      "action": "create",
      "environment": "region-1",
      "namespace": "sim-resources"
    },
    "creation_parameters": {
      "sets": 5,
      "networkcount": 2,
      "endpointcount": 2,
      "loadbalancer": true,
      "batchapply": true,
      "vnitype": "cvsi"
    },
    "deletion_parameters": {
      "force_delete": true
    }
  }
  ```

- **Error Handling:** If a resource fails to apply, the script will automatically save its YAML to a file named `error_creating_<KIND>_<NAME>.yaml` in the current directory. This is extremely useful for debugging failed deployments.

- **YAML Generation:** When generating YAML files (e.g., with `-a`), the script prefixes filenames with numbers (e.g., `01_router_...`, `05_network_...`). This prefix indicates the creation order to ensure dependencies are handled correctly when applying resources manually or in batches.

- **Image Management (`changeimage`):** This command modifies the live deployment YAML and depends on the `./scripts/gen_deployment.py` script. Before applying changes, it creates a backup named `deployment.yaml.bak`. The `--revert` flag restores from this backup.

- **Dependency on `applied_resources.txt`:** Actions like `manipulate` and `delete --deletefromfile` rely on the `applied_resources.txt` file, which is generated by the `create` command. Ensure you have run a `create` operation first before using these features.

---

## Contact

For questions, bug reports, or feature requests, please contact: @hariharen9 (GitHub)

---
