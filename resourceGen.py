import difflib
import subprocess
import os
import time
import uuid
import sys
from datetime import datetime
import tempfile
import json
import yaml
import random
import string
import ipaddress
import re
import shutil
import multiprocessing
from utils import *

# ---------------------------------RESOURCE CREATION-------------------------------------
#----------------------------------------------------------------------------------------
#   ROUTER
#----------------------------------------------------------------------------------------
def create_router():
    if vni_type != 'cvsi':
        print_green(f"\nCreating Resources for VPCID: {vpcid}")
        print_green(f"\nCreating Router")

        reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        router_template = template_data["routerTemplate"].copy()
        router_template["metadata"]["annotations"]["RequestID"] = reqid
        router_template["metadata"]["namespace"] = ns
        router_template["metadata"]["name"] = rName
        router_template["metadata"]["labels"]["VPCID"] = vpcid
        router_template["spec"]["vpcid"] = vpcid
        router_template["spec"]["routeDistinguisher"] = generate_route_distinguisher(mz)
        router_template["spec"]["addressPrefixes"] = router_address_prefixes
        router_template["spec"]["serviceGatewayIP"] = serviceGatewayIP_address
        router_template["spec"]["serviceGatewayStaticRoutes"] = generate_serviceGatewayStaticRoutes(routerIndex)

        applying(router_template)

#----------------------------------------------------------------------------------------
#  ClusterVSI
#----------------------------------------------------------------------------------------
def create_clusterVSI():
    if vni_type == 'cvsi':
        reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

        global cvsiName
        cvsiName = f"{rPrefix}-{str(uuid.uuid4())}"


        print_green("\nCreating ClusterVSIs (For H100 Support)")

        cvsi_template = template_data["clusterNetworkTemplate"].copy()

        cvsi_template["metadata"]["annotations"]["RequestID"] = reqid
        cvsi_template["metadata"]["namespace"] = ns
        cvsi_template["metadata"]["name"] = cvsiName
        cvsi_template["metadata"]["labels"]["VPCID"] = vpcid
        cvsi_template["spec"]["zone"] = mz

        applying(cvsi_template)

#----------------------------------------------------------------------------------------
#   ROUTING TABLE
#----------------------------------------------------------------------------------------
def create_routing_table():
    print_green("\nCreating CWRouting Tables")
    reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    rtr_table_template = template_data["routingTableTemplate"].copy()
    rtr_table_template["metadata"]["namespace"] = ns
    rtr_table_template["metadata"]["name"] = rtrTableName
    rtr_table_template["spec"]["vpcid"] = vpcid
    rtr_table_template["metadata"]["labels"]["VPCID"] = vpcid
    if vni_type == 'cvsi':
        rtr_table_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName

    for i, route in enumerate(rtr_table_template["spec"]["routes"]):
        route["uuid"] = f"{rPrefix}-{str(uuid.uuid4())}"
        octet2, octet3 = get_octets(routerIndex + i)
        route["destinationCIDR"] = f"192.{octet2}.{octet3}.0/24"
        if route["action"] == "deliver":
            octet3_ip, octet4_ip = get_octets(routerIndex + i)
            route["nextHopIP"] = f"192.211.{octet3_ip}.{octet4_ip}"

    applying(rtr_table_template)

#----------------------------------------------------------------------------------------
#   INGRESS ROUTING TABLE
#----------------------------------------------------------------------------------------
def create_ingress_routing_table():
    print_green("\nCreating Ingress Routing Tables")
    reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    ingress_rt_template = template_data["ingressRoutingTableTemplate"].copy()

    ingress_rt_template["metadata"]["namespace"] = ns
    ingress_rt_template["metadata"]["name"] = ingressRTName
    ingress_rt_template["spec"]["vpcid"] = vpcid
    ingress_rt_template["metadata"]["labels"]["VPCID"] = vpcid
    if vni_type == 'cvsi':
        ingress_rt_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName

    for i, route in enumerate(ingress_rt_template["spec"]["routes"]):
        route["uuid"] = f"{rPrefix}-{str(uuid.uuid4())}"
        octet2, octet3 = get_octets(routerIndex + i)
        route["destinationCIDR"] = f"192.{octet2}.{octet3}.0/24"
        if route["action"] == "deliver":
            octet3_ip, octet4_ip = get_octets(routerIndex + i)
            route["nextHopIP"] = f"192.222.{octet3_ip}.{octet4_ip}"

    applying(ingress_rt_template)

#----------------------------------------------------------------------------------------
#   SECURITY GROUPS
#----------------------------------------------------------------------------------------
def create_security_groups():
    print_green("\nCreating Security Groups")
    for sgnum in range(1, 3):
        reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        global sgName
        sgName = f"{rPrefix}-{str(uuid.uuid4())}"

        sg_template = template_data["securityGroupTemplate"].copy()

        sg_template["metadata"]["namespace"] = ns
        sg_template["metadata"]["name"] = sgName
        sg_template["metadata"]["annotations"]["RequestID"] = reqid
        sg_template["metadata"]["labels"]["ResourceName"] = sgName
        sg_template["metadata"]["labels"]["VPCID"] = vpcid
        if vni_type == 'cvsi':
            sg_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName
        sg_template["spec"]["vpcid"] = vpcid
        for rule in sg_template["spec"]["rules"]:
            rule["uid"] = f"{rPrefix}-{str(uuid.uuid4())}"

        applying(sg_template)

#----------------------------------------------------------------------------------------
#   NACLs
#----------------------------------------------------------------------------------------
def create_nacls():

    print_green("\nCreating NACLs")
    for naclnum in range(1, 3):
        reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        global naclName
        naclName = f"{rPrefix}-{str(uuid.uuid4())}"

        nacl_template = template_data["networkACLTemplate"].copy()

        nacl_template["metadata"]["namespace"] = ns
        nacl_template["metadata"]["name"] = naclName
        nacl_template["metadata"]["annotations"]["description"] = "Network ACL"
        nacl_template["metadata"]["labels"]["VPCID"] = vpcid
        if vni_type == 'cvsi':
            nacl_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName
        nacl_template["spec"]["vpcid"] = vpcid
        for rule in nacl_template["spec"]["rules"]:
            rule["uid"] = f"{rPrefix}-{str(uuid.uuid4())}"

        applying(nacl_template)

#----------------------------------------------------------------------------------------
#   NETWORK FILES
#----------------------------------------------------------------------------------------
def create_networks():

    print_green("\nCreating Networks")
    for netnum in range(1, nwcount + 1):
        reqid = f"{netnum}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        global nw
        nw = f"{mz}-{str(uuid.uuid4())}"
        subnet = local_net_prefixes[netnum - 1]
        nws.append(nw)

        nw_template = template_data["networkTemplate"].copy()

        nw_template["metadata"]["annotations"]["RequestID"] = reqid
        nw_template["metadata"]["labels"]["VPCID"] = vpcid
        if vni_type == 'cvsi':
            nw_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName
        nw_template["metadata"]["namespace"] = ns
        nw_template["metadata"]["name"] = nw
        nw_template["metadata"]["uid"] = f"{str(uuid.uuid4())}"
        nw_template["spec"]["routerName"] = rName
        nw_template["spec"]["cidr"] = subnet
        nw_template["spec"]["aclName"] = naclName
        nw_template["spec"]["publicGatewayUID"] = f"{rPrefix}-{str(uuid.uuid4())}"
        network_range = ipaddress.ip_network(serviceGatewayIP_range)
        public_gw_ip = network_range.network_address + netnum
        nw_template["spec"]["publicGatewayIP"] = str(public_gw_ip)
        nw_template["spec"]["routingTableName"] = rtrTableName

        applying(nw_template)

        if vni_type in ['cvsi', 'xacc', 'base']:
            global vnic_names
            vnic_names = []
            nodes = get_compute_nodes(specificnode, excludenode)
            for i, node in enumerate(nodes):
                vnic_name = f"{mz}-{str(uuid.uuid4())}"
                vnic_names.append(vnic_name)
                print(f"vnic name: {vnic_name}")

#----------------------------------------------------------------------------------------
#   FOREIGN NETWORK FILES
#----------------------------------------------------------------------------------------

def create_foreign_networks():
    print_green("\nAttempting to Create Foreign Networks")
    
    fnw_prefix = get_fnw_prefix()
    if not fnw_prefix:
        return

    for netnum in range(1, nwcount + 1):
        reqid = f"{netnum}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"

        fnw = f"{fnw_prefix}-{str(uuid.uuid4())}"
        subnet = foreign_net_prefixes[netnum - 1]
        print(f"for {subnet}")

        fnw_template = template_data["foreignNetworkTemplate"].copy()

        fnw_template["metadata"]["namespace"] = ns
        fnw_template["metadata"]["name"] = fnw
        fnw_template["metadata"]["annotations"]["RequestID"] = reqid
        fnw_template["metadata"]["labels"]["VPCID"] = vpcid
        fnw_template["spec"]["routerName"] = rName
        fnw_template["spec"]["cidr"] = subnet
        fnw_template["spec"]["aclName"] = naclName
        fnw_template["spec"]["publicGatewayUID"] = f"{rPrefix}-{str(uuid.uuid4())}"
        new_octet3, octet4 = get_octets(netnum)
        fnw_template["spec"]["publicGatewayIP"] = f"192.22.{new_octet3}.{octet4}"
        fnw_template["spec"]["routingTableName"] = rtrTableName

        applying(fnw_template)



#----------------------------------------------------------------------------------------
#   VIRTUAL NETWORK / VNICs
#----------------------------------------------------------------------------------------


def create_vnics():
    print_green("\nCreating VirtualNics (VNIC)")
    nodes = get_compute_nodes(specificnode, excludenode)
    # Filter nodes based on specificnode and excludenode
    if specificnode:
        nodes = [node for node in nodes if node.decode('utf-8') in specificnode]
    if excludenode:
        nodes = [node for node in nodes if node.decode('utf-8') not in excludenode]

    print(f"Number of Nodes:{len(nodes)}")
    print(f"Nodes: {nodes}")

    if vni_type in [None, 'smt']:
        global vnic_names
        vnic_names = []
    
    vnic_counter = 0

    # Verifying for DualNICs
    def verifydnic(node):
        global dnic
        node_name_str = node.decode('utf-8')
        dnic = False 

        commandtogetnodeyaml = f"kubectl get node {node_name_str} -o yaml"
        node_yaml_str = run_command_strip(commandtogetnodeyaml)

        if not node_yaml_str:
            print_red(f"Could not fetch YAML for node {node_name_str} to check DNIC status.")
            return

        try:
            node_yaml = yaml.safe_load(node_yaml_str)
            if not node_yaml or 'metadata' not in node_yaml:
                print_red(f"Node {node_name_str} YAML is malformed or lacks metadata.")
                return

            # Check 1: sim-ns.smartnic=true label (for ELBA DNICs)
            labels = node_yaml.get('metadata', {}).get('labels', {})
            if labels.get('sim-ns.smartnic') == 'true':
                print(f"Node {node_name_str} identified as DNIC (via sim-ns.smartnic=true label).")
                dnic = True
                return

            # Check 2: sim-ns.nics annotation (for other DNICs)
            annotations = node_yaml.get('metadata', {}).get('annotations', {})
            if 'sim-ns.nics' in annotations:
                nics_json_str = annotations['sim-ns.nics']
                try:
                    nics_list = json.loads(nics_json_str)
                    if isinstance(nics_list, list) and len(nics_list) > 1:
                        print(f"Node {node_name_str} identified as DNIC (via sim-ns.nics annotation with {len(nics_list)} NICs).")
                        dnic = True
                        return
                except json.JSONDecodeError:
                    print_red(f"Error decoding sim-ns.nics JSON for node {node_name_str}. Will not be considered DNIC by this check.")
            
            if not dnic:
                 print(f"Node {node_name_str} not a DNIC Node, continuing with single NIC configuration.")
                 pass

        except Exception as e:
            print_red(f"Unexpected error verifying DNIC for node {node_name_str}: {e}")

    # Loop over nodes and endpoints, not networks
    for i, node in enumerate(nodes):
        for epnum in range(1, epcount + 1):
            
            # Round-robin network assignment
            if not nws:
                print_red("Error: No networks available to assign to VNICs. Exiting.")
                sys.exit(1)
            assigned_nw = nws[vnic_counter % len(nws)]
            print_green(f"VNIC #{vnic_counter + 1}: Assigning to node '{node.decode('utf-8')}' in network '{assigned_nw}'")

            reqid = f"{i}-{epnum}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
            vm_uuid = str(uuid.uuid4())
            uuid_val = str(uuid.uuid4())
            vm_name = f"{mz}_{vm_uuid}"

            # Simplified and corrected name generation
            current_vnic_name = ""
            # For VNI types, names are pre-populated. The mutual exclusion in netsim.py ensures ec=1.
            if vni_type in ['cvsi', 'xacc', 'base']:
                current_vnic_name = vnic_names[i]
            # For non-VNI types, generate a unique name for every VNIC.
            else: # vni_type is None or 'smt'
                global vnic_name
                vnic_name = f"{mz}-{uuid_val}"
                vnic_names.append(vnic_name)
                current_vnic_name = vnic_name

            vnic_template = template_data["virtualNicTemplate"].copy()

            vnic_template["metadata"]["annotations"]["RequestID"] = reqid
            vnic_template["metadata"]["namespace"] = ns
            vnic_template["metadata"]["name"] = current_vnic_name
            vnic_template["metadata"]["labels"]["OwnerNamespace"] = ns
            vnic_template["metadata"]["labels"]["ResourceGroup"] = resourceGroup
            vnic_template["metadata"]["labels"]["ResourceID"] = f"{mz}-{resourceID}"
            vnic_template["metadata"]["labels"]["VPCID"] = vpcid
            vnic_template["metadata"]["labels"]["vm_name"] = vm_name
            vnic_template["metadata"]["labels"]["InstanceID"] = vm_name
            vnic_template["metadata"]["labels"]["selflink"] = current_vnic_name
            vnic_template["spec"]["name"] = current_vnic_name
            vnic_template["spec"]["network"]["Name"] = assigned_nw # Use the round-robin assigned network
            vnic_template["spec"]["network"]["Namespace"] = ns
            vnic_template["spec"]["node"]["name"] = node.decode('utf-8')
            octet3, octet4 = get_octets(routerIndex + 1)
            vnic_template["spec"]["floatingIP"] = f"192.{epnum}.{octet3}.{octet4}"
            
            # VNI-linking logic is safe due to the mutual exclusion check in netsim.py
            if vni_type == 'cvsi':
                vnic_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName
                if "virtualNetworkInterface" not in vnic_template["spec"]:
                    vnic_template["spec"]["virtualNetworkInterface"] = {}
                vnic_template["spec"]["virtualNetworkInterface"]["Name"] = vni_names[i]
                vnic_template["spec"]["virtualNetworkInterface"]["Namespace"] = ns
            
            if vni_type == 'base':
                if "virtualNetworkInterface" not in vnic_template["spec"]:
                    vnic_template["spec"]["virtualNetworkInterface"] = {}
                vnic_template["spec"]["virtualNetworkInterface"]["Name"] = vni_names[i]
                vnic_template["spec"]["virtualNetworkInterface"]["Namespace"] = ns

            if vni_type == 'xacc':
                if "virtualNetworkInterface" not in vnic_template["spec"]:
                    vnic_template["spec"]["virtualNetworkInterface"] = {}
                vnic_template["spec"]["virtualNetworkInterface"]["Name"] = vni_names[i]
                vnic_template["spec"]["virtualNetworkInterface"]["Namespace"] = xacc_namespace
                print_green(f"\nUsing X-ACC Namespace: {xacc_namespace} for VNI {vni_names[i]}")

            vnic_template["spec"]["virtualMachine"]["Name"] = vm_name
            vnic_template["spec"]["virtualMachine"]["Namespace"] = ns
            vnic_template["spec"]["sgNames"] = [f"{sgName}"]

            verifydnic(node)
            
            if dnic: # Will fetch and add TunnelEndpointIP for VNICs in case of DNIC nodes.
                node_name_str_for_dnic = node.decode('utf-8')
                print(f"Node {node_name_str_for_dnic} is DNIC. Attempting to fetch TunnelEndpointIP from sim-ns.nics.")
                
                commandtogetip = f"kubectl get node {node_name_str_for_dnic} -o yaml"
                command_output = run_command_strip(commandtogetip)

                if command_output:
                    try:
                        yaml_output = yaml.safe_load(command_output)
                        if (yaml_output and 'metadata' in yaml_output and 'annotations' in yaml_output['metadata'] and 'sim-ns.nics' in yaml_output['metadata']['annotations']):
                            nics_json_str = yaml_output['metadata']['annotations']['sim-ns.nics']
                            nics_list = json.loads(nics_json_str)
                            
                            if isinstance(nics_list, list) and nics_list:
                                selected_tunnelendpoint_ip = None
                                for nic_item in nics_list:
                                    if isinstance(nic_item, dict) and 'TunnelEndpointIP' in nic_item and nic_item['TunnelEndpointIP']:
                                        selected_tunnelendpoint_ip = nic_item['TunnelEndpointIP']
                                        print(f"Using TunnelEndpointIP: {selected_tunnelendpoint_ip} from sim-ns.nics for node {node_name_str_for_dnic}.")
                                        break
                                
                                if selected_tunnelendpoint_ip:
                                    vnic_template["spec"]["tunnelEndpointIP"] = selected_tunnelendpoint_ip
                        else:
                            # If dnic was true due to smartnic label, and sim-ns.nics isn't present/usable for TEPIP.
                            print_red(f"sim-ns.nics annotation not found or is malformed for DNIC node {node_name_str_for_dnic}; cannot set TunnelEndpointIP from it.")
                    
                    except Exception as e:
                        print_red(f"Error processing TunnelEndpointIP for DNIC node {node_name_str_for_dnic}: {e}")
                        
                else:
                    print_red(f"Failed to get YAML for DNIC node {node_name_str_for_dnic} to fetch TunnelEndpointIP.")
            
            if vni_type == 'cvsi':
                yaml_str = yaml.dump(vnic_template, default_flow_style=False)
                namespace, kind, idName = extract_metadata(vnic_template)

                folder_name = f"cvsi_{kind}s"
                if not os.path.exists(folder_name):
                    os.makedirs(folder_name)

                vnics_names_file_path = os.path.join(folder_name, "vnics_names_file.txt")
                with open(vnics_names_file_path, "a") as vnics_names_file:
                    vnics_names_file.write(f"{idName}\n")
                print(f"Added the VNIC name - {idName} to the vnics_names_file.txt")

                resource_yaml_path = os.path.join(folder_name, f"{idName}.yaml")
                with open(resource_yaml_path, "w") as resources_yaml:
                    resources_yaml.write(yaml_str)

            # Apply the VNIC after all modifications as needed.
            applying(vnic_template)
            vnic_counter += 1

    print_green(f"VNIC names - {vnic_names}")

#----------------------------------------------------------------------------------------
#   LB (Load Balancer) Files
#----------------------------------------------------------------------------------------

def create_lb():
    if loadbalancer in ["yes", "y"]:
        print_green("\nCreating LBs (Load Balancer)")

        global lb_name
        global lb_pool_name
        global lb_listener_name
        lb_name = f"{rPrefix}-{str(uuid.uuid4())}"
        lb_pool_name = f"{rPrefix}-{str(uuid.uuid4())}"
        lb_listener_name = f"{rPrefix}-{str(uuid.uuid4())}"

        lb_template = template_data["loadBalancerTemplate"].copy()

        lb_template["metadata"]["namespace"] = ns
        lb_template["metadata"]["name"] = lb_name
        lb_template["spec"]["vpcid"] = vpcid
        lb_template["metadata"]["labels"]["VPCID"] = vpcid
        lb_template["spec"]["ipv4"] = serviceGatewayIP_address

        applying(lb_template)
    else:
        return

#----------------------------------------------------------------------------------------
#   LB POOL FILES
#----------------------------------------------------------------------------------------
def create_lb_pool():
    if loadbalancer in ["yes", "y"]:
        print_green("\nCreating LBPools (Load Balancer Pool)")

        lbpool_template = template_data["lbPoolTemplate"].copy()

        lbpool_template["metadata"]["namespace"] = ns
        lbpool_template["metadata"]["name"] = lb_pool_name
        lbpool_template["metadata"]["labels"]["VPCID"] = vpcid
        lbpool_template["spec"]["vpcid"] = vpcid
        lbpool_template["spec"]["lbName"] = lb_name  # Update with the LB name as needed

        applying(lbpool_template)
    else:
        return


#----------------------------------------------------------------------------------------
#   LB POOL MEMBERS
#----------------------------------------------------------------------------------------
def create_lb_pool_members():
    if loadbalancer in ["yes", "y"]:
        print_green(f"\nCreating LBPoolMembers (Load Balancer Pool Members)")

        lbpoolmember_template = template_data["lbPoolMemberTemplate"].copy()

        for num, vnic_name in enumerate(vnic_names):

            lbpoolmember_template["metadata"]["namespace"] = ns
            lbpoolmember_template["metadata"]["name"] = f"{mz}-{str(uuid.uuid4())}"
            lbpoolmember_template["metadata"]["labels"]["VPCID"] = vpcid
            lbpoolmember_template["spec"]["lbPoolName"] = lb_pool_name
            lbpoolmember_template["spec"]["vnicId"] = vnic_name

            applying(lbpoolmember_template)
    else:
        return

#----------------------------------------------------------------------------------------
#   LB LISTENERS
#----------------------------------------------------------------------------------------
def create_lb_listeners():
    if loadbalancer in ["yes", "y"]:
        print_green("\nCreating LBListeners (Load Balancer Listeners)")

        lblistener_template = template_data["lbListenerTemplate"].copy()

        lblistener_template["metadata"]["namespace"] = ns
        lblistener_template["metadata"]["name"] = lb_listener_name
        lblistener_template["metadata"]["labels"]["VPCID"] = vpcid
        lblistener_template["spec"]["vpcid"] = vpcid
        lblistener_template["spec"]["lbName"] = lb_name
        lblistener_template["spec"]["defaultPoolID"] = lb_pool_name

        applying(lblistener_template)
    else:
        return

#----------------------------------------------------------------------------------------
#   Reserved IPs
#----------------------------------------------------------------------------------------
def create_reserved_ip():
    print_green("\nCreating ReservedIps")
    nodes = get_compute_nodes(specificnode, excludenode)
    nodeslen = len(nodes)
    global rip_names
    global epgw_names
    global vni_uuids
    global vni_names
    vni_names = []
    vni_uuids = []
    rip_names = []
    epgw_names = []
    if ripcount > nodeslen:
        print("Using RIP count")
        for ripnum in range(0, ripcount + 2):
            epgw_name = f"{mz}-{str(uuid.uuid4())}"
            epgw_names.append(epgw_name)
            rip_name = f"{mz}-{str(uuid.uuid4())}"
            rip_names.append(rip_name)
            rip_uuid = str(uuid.uuid4())
            vni_uuid = str(uuid.uuid4())
            vni_uuids.append(vni_uuid)
            vni_name = f"{mz}-{str(uuid.uuid4())}"
            vni_names.append(vni_name)

            rip_template = template_data["reservedIPTemplate"].copy()

            rip_template["metadata"]["namespace"] = ns
            rip_template["metadata"]["name"] = rip_name
            rip_template["metadata"]["uid"] = rip_uuid
            rip_template["metadata"]["labels"]["VPCID"] = vpcid
            rip_template["metadata"]["labels"]["ZoneBitmask"] = mz
            rip_template["spec"]["networkName"] = nw
            rip_template["spec"]["resourceAssociation"]["associationType"] = "vni"
            rip_template["spec"]["resourceAssociation"]["id"] = vni_uuid
            rip_template["spec"]["vpcid"] = vpcid

            applying(rip_template)
    else:
        print("Using Nodes Count")
        for ripnum in range(0, nodeslen + 1):
            epgw_name = f"{mz}-{str(uuid.uuid4())}"
            epgw_names.append(epgw_name)
            rip_name = f"{mz}-{str(uuid.uuid4())}"
            rip_names.append(rip_name)
            rip_uuid = str(uuid.uuid4())
            vni_uuid = str(uuid.uuid4())
            vni_uuids.append(vni_uuid)
            vni_name = f"{mz}-{str(uuid.uuid4())}"
            vni_names.append(vni_name)

            rip_template = template_data["reservedIPTemplate"].copy()

            rip_template["metadata"]["namespace"] = ns
            rip_template["metadata"]["name"] = rip_name
            rip_template["metadata"]["uid"] = rip_uuid
            rip_template["metadata"]["labels"]["VPCID"] = vpcid
            rip_template["metadata"]["labels"]["ZoneBitmask"] = mz
            rip_template["spec"]["networkName"] = nw
            rip_template["spec"]["resourceAssociation"]["associationType"] = "vni"
            rip_template["spec"]["resourceAssociation"]["id"] = vni_uuid
            rip_template["spec"]["vpcid"] = vpcid

            applying(rip_template)

#----------------------------------------------------------------------------------------
#   Share Mount Targets (SMTs)
#----------------------------------------------------------------------------------------
def create_smt():
    if vni_type == 'smt':
        def generate_random_mountpath():
            chars = string.ascii_lowercase + string.digits + '_'
            random_string = ''.join(random.choice(chars) for _ in range(36))
            return f"/b{random_string[:8]}_{random_string[8:12]}_{random_string[12:16]}_{random_string[16:20]}_{random_string[20:]}"

        print_green("\nCreating SMTs")
        nodes = get_compute_nodes(specificnode, excludenode)
        octet2, octet3 = get_octets(routerIndex)

        global smt_names
        smt_names = []

        for i, node in enumerate(nodes):
            smt_name = f"{mz}-{str(uuid.uuid4())}"
            smt_names.append(smt_name)
            eVPNprefixValue = f"23.{octet2}.{octet3}.0/24"
            
            smt_template = template_data["shareMountTargetTemplate"].copy()
            
            smt_template["metadata"]["namespace"] = ns
            smt_template["metadata"]["name"] = smt_name
            smt_template["metadata"]["annotations"]["V3MountPath"] = generate_random_mountpath()
            smt_template["metadata"]["labels"]["VPCID"] = vpcid
            smt_template["metadata"]["labels"]["VirtualNetworkInterfaceID"] = vni_names[i]
            smt_template["metadata"]["labels"]["ZoneBitmask"] = mz
            smt_template["spec"]["eVPNPrefixes"][mz] = [eVPNprefixValue]

            applying(smt_template)

#----------------------------------------------------------------------------------------
#   Virtual Network Interface (VNIs)
#----------------------------------------------------------------------------------------
def create_vni():

    print_green("\nCreating VNIs")

    nodes = get_compute_nodes(specificnode, excludenode)

    for i, node in enumerate(nodes):

        global vni_name
        vni_name = f"{mz}-{str(uuid.uuid4())}"
        primaryrip_name = f"{mz}-{str(uuid.uuid4())}"
        
        vni_template = template_data["virtualNetworkInterfaceTemplate"].copy()

        vni_template["metadata"]["namespace"] = ns
        vni_template["metadata"]["name"] = vni_names[i]
        vni_template["metadata"]["uid"] = vni_uuids[i]
        vni_template["metadata"]["labels"]["VPCID"] = vpcid
        
        octet3, octet4 = get_octets(routerIndex)
        fip_octet4 = (octet4 + i) % 256 # Add node index for unique FIPs within the VPC
        vni_template["spec"]["floatingIPs"] = [f"52.118.{octet3}.{fip_octet4}"]

        vni_template["spec"]["networkName"] = nw
        vni_template["spec"]["primaryReservedIPName"] = rip_names[i]
        if vni_type == 'cvsi':
            vni_template["metadata"]["labels"]["ClusterNetworkID"] = cvsiName
            vni_template["spec"]["target"]["name"] = vnic_names[i]
            vni_template["spec"]["target"]["type"] = "ClusterNetworkAttachment"
        elif vni_type == 'smt':
            vni_template["spec"]["target"]["name"] = smt_names[i]
            vni_template["spec"]["target"]["type"] = "ShareMountTarget"
        elif vni_type == 'base':
            vni_template["spec"]["target"]["name"] = vnic_names[i]
            vni_template["spec"]["target"]["type"] = "InstanceNetworkAttachment"
        elif vni_type == 'xacc':
            vni_template["metadata"]["labels"]["X-ACCOUNT-ID"] = ns
            vni_template["metadata"]["namespace"] = xacc_namespace
            print_green(f"\nCreating VNI in XACC Namespace: {xacc_namespace}")
            vni_template["spec"]["target"]["name"] = vnic_names[i]
            vni_template["spec"]["target"]["type"] = "InstanceNetworkAttachment"

        vni_template["spec"]["securityGroupNames"] = [f"{sgName}"]

        applying(vni_template)
        
        # if vni_type == 'xacc':
        #     global nif_names, nep_data, nep_names  # Declare that these variables are global
        #     nif_names = []
        #     nep_names = []
        #     nep_data = [] 
        # Not needed as of now, NIF and NEP will not be created manually, so disabled in creation sequence.
        
#----------------------------------------------------------------------------------------
#   Public Address Range (PARs)
#----------------------------------------------------------------------------------------
def create_public_address_range():
    global mz
    global ns
    global parcount
    global rPrefix
    global vpcid

    octet2, octet3 = get_octets(routerIndex)
    
    if parcount == 0:
        return

    print_green("\nCreating Public Address Range")

    for parIdx in range(0, parcount):
        par_template = template_data["publicAddressRangeTemplate"].copy()
        par_template["metadata"]["labels"]["VPCID"] = vpcid
        par_template["metadata"]["name"] = f"{rPrefix}-{str(uuid.uuid4())}"
        par_template["metadata"]["namespace"] = ns
        par_template["spec"]["cidr"] = f"10.{octet2}.{octet3}.0/24"
        par_template["spec"]["vpcid"] = vpcid
        par_template["spec"]["zone"] = mz

        applying(par_template)
           
#----------------------------------------------------------------------------------------
#   FlowLog
#----------------------------------------------------------------------------------------
def create_flowlog():
    if flowlog_kind is None:
        return
    
    target_ids = []

    if flowlog_kind == "Router":
        target_ids = [rName]
    elif flowlog_kind == "Network":
        if not nws:
            print_red("Error: Cannot target Network with --flowlog. No Networks created.")
            return
        target_ids = nws
    elif flowlog_kind == "VirtualNic":
        if nep_nif:
            print_red("Error: Cannot target VirtualNic with --flowlog when -nn (skip VNIC) is used.")
            return
        if not vnic_names:
            print_red("Error: Cannot target VirtualNic with --flowlog. No VNICs created.")
            return
        if vni_type in ['base', 'cvsi', 'xacc']:
             nodes = get_compute_nodes(specificnode, excludenode)
             target_ids = vnic_names[:len(nodes)]
        else:
             target_ids = vnic_names
    elif flowlog_kind == "VirtualNetworkInterface":
        if vni_type is None:
            print_red("Error: Cannot target VirtualNetworkInterface with --flowlog without -vni flag.")
            return
        if not vni_names:
            print_red("Error: Cannot target VirtualNetworkInterface with --flowlog. No VNIs created.")
            return
        nodes = get_compute_nodes(specificnode, excludenode)
        target_ids = vni_names[:len(nodes)]

    if flowlog_one and target_ids:
        target_ids = target_ids[:1]
        print_green(f"\nCreating 1 FlowLog for {flowlog_kind} (limited by -one)")
    else:
        print_green(f"\nCreating FlowLogs for {len(target_ids)} {flowlog_kind}(s)")

    for target_id in target_ids:
        flowlog_name = f"{rPrefix}-{str(uuid.uuid4())}"
        
        flowlog_template = template_data["flowLogTemplate"].copy()
        flowlog_template["metadata"]["namespace"] = ns
        flowlog_template["metadata"]["name"] = flowlog_name
        flowlog_template["metadata"]["labels"]["VPCID"] = vpcid
        flowlog_template["spec"]["vpcid"] = vpcid
        
        # Set the target kind and identifier based on the flowlog_kind
        flowlog_template["spec"]["target"]["kind"] = flowlog_kind
        flowlog_template["spec"]["target"]["identifier"] = target_id
        
        flowlog_template["spec"]["cosBucket"]["name"] = "test-cos-bucket"
        flowlog_template["spec"]["cosBucket"]["endpoint"] = "localhost"

        if included_protocols:
            flowlog_template["spec"]["includedProtocols"] = included_protocols
        
        if excluded_protocols:
            flowlog_template["spec"]["excludedProtocols"] = excluded_protocols

        applying(flowlog_template)

#----------------------------------------------------------------------------------------
#   Endpoint Gateway (EPGW)
#----------------------------------------------------------------------------------------
def create_endpoint_gateway():
    if epgwcount > 0:
        print_green(f"\nCreating {epgwcount} Endpoint Gateway(s) (EPGW)")

        # Give a warning if not in apply mode, since IP cannot be fetched.
        if not do_apply and epgwcount > 0:
            print_yellow("Warning: Not in sequential --apply mode. The 'ipv4' field in Endpoint Gateway(s) will be left blank.")

        for i in range(epgwcount):
            
            # Applying RIP first
            epgw_rip_name = f"{mz}-{str(uuid.uuid4())}"
            rip_template = template_data["reservedIPTemplate"].copy()
            rip_template["metadata"]["namespace"] = ns
            rip_template["metadata"]["name"] = epgw_rip_name
            rip_template["metadata"]["labels"]["VPCID"] = vpcid
            rip_template["metadata"]["labels"]["ZoneBitmask"] = mz
            rip_template["spec"]["networkName"] = nws[i % len(nws)]
            rip_template["spec"]["vpcid"] = vpcid
            if "resourceAssociation" in rip_template["spec"]:
                del rip_template["spec"]["resourceAssociation"]

            rip_applied_successfully = True
            if do_apply:
                rip_yaml_str = yaml.dump(rip_template, default_flow_style=False)
                rip_apply_command = f"kubectl apply -f - <<EOF\n{rip_yaml_str}\nEOF"
                rip_result = apply(rip_apply_command, "ReservedIP")
                if rip_result.returncode != 0:
                    print_red(f"  -> Failed to create ReservedIP '{epgw_rip_name}'. Skipping associated EPGW.")
                    rip_applied_successfully = False
            
            if not rip_applied_successfully:
                continue

            applying(rip_template)

            ipv4_from_status = None
            if do_apply:
                ipv4_from_status = get_rip_ip_address(epgw_rip_name, ns)
                if not ipv4_from_status:
                    print_red(f"CRITICAL: Failed to acquire IP for ReservedIP '{epgw_rip_name}' after timeout. Skipping this EPGW.")
                    continue

            # Applying EPGW next
            epgw_name = f"{rPrefix}-{str(uuid.uuid4())}"
            epgw_template = template_data["endpointGatewayTemplate"].copy()

            epgw_template["metadata"]["namespace"] = ns
            epgw_template["metadata"]["name"] = epgw_name
            epgw_template["metadata"]["labels"]["VPCID"] = vpcid
            epgw_template["spec"]["vpcid"] = vpcid
            epgw_template["spec"]["sgNames"] = [sgName] if sgName else []

            if epgw_template["spec"]["virtualEndpoints"]:
                vep = epgw_template["spec"]["virtualEndpoints"][0]
                vep["networkName"] = nws[i % len(nws)]
                vep["reservedIPName"] = epgw_rip_name
                vep["ipv4"] = ipv4_from_status if ipv4_from_status else ""
                
                static_routes = generate_serviceGatewayStaticRoutes(routerIndex)
                if static_routes:
                    service_cidr = static_routes[i % len(static_routes)]
                    network = ipaddress.ip_network(service_cidr)
                    vep["serviceDestIP"] = str(network.network_address + 5 + i) # Assign unique IP within the CIDR
                else:
                    octet3, _ = get_octets(routerIndex)
                    vep["serviceDestIP"] = f"192.21.{octet3}.{100 + i}"

            applying(epgw_template)
    else:
        return
           
# #----------------------------------------------------------------------------------------
# #   Network Endpoints (NEPs)
# #----------------------------------------------------------------------------------------

def create_networkEndpoint():
    print_green("\nCreating Network Endpoints (NEP)")

    global nif_names, nep_names, nep_data, vnic_names
    nif_names = []
    nep_names = []
    nep_data = []

    nodes = get_compute_nodes(specificnode, excludenode)
    
    # If skipping VNIC creation, generate mock VNIC names
    if nep_nif and not vnic_names:
        vnic_names = []
        print_green("Generating Mock VNIC Names for NEP/NIF creation...")
        for i in range(len(nodes)):
            vnic_name = f"{mz}-{str(uuid.uuid4())}"
            vnic_names.append(vnic_name)

    for i in range(len(nodes)):
        local_vnic_name = vnic_names[i]
        local_nif_name = add_suffix_to_prefix(local_vnic_name, 5)
        nif_names.append(local_nif_name)
        local_nep_name = add_suffix_to_prefix(local_vnic_name, 5)
        nep_names.append(local_nep_name)

    for i in range(len(nodes)):
        nep_uuid = str(uuid.uuid4())
        nep_name = nep_names[i]
        nep_template = template_data["networkEndpointTemplate"].copy()

        nep_template["metadata"]["namespace"] = ns
        nep_template["metadata"]["name"] = nep_name
        nep_template["metadata"]["uid"] = nep_uuid
        nep_template["metadata"]["labels"]["VPCID"] = vpcid
        nep_template["metadata"]["labels"]["ResourceID"] = vnic_names[i]
        
        if len(nws) > 0:
            nep_template["spec"]["networkname"] = nws[i % len(nws)]
        
        nep_template["spec"]["networkInterfaceNames"] = [nif_names[i]]
        
        if vni_type == 'xacc':
            if "virtualNetworkInterfaceNS" not in nep_template["spec"]:
                nep_template["spec"]["virtualNetworkInterfaceNS"] = {}
            nep_template["spec"]["virtualNetworkInterfaceNS"]["Name"] = vni_names[i]
            nep_template["spec"]["virtualNetworkInterfaceNS"]["Namespace"] = xacc_namespace
        elif vni_type == 'base' or vni_type == 'cvsi' or vni_type == 'smt':
            nep_template["spec"]["virtualNetworkInterface"] = vni_names[i]
        else:
            if "virtualNetworkInterface" in nep_template["spec"]:
                del nep_template["spec"]["virtualNetworkInterface"]

        applying(nep_template)
        
        # Save data for NIF creation
        nep_data.append({"name": nep_name, "uuid": nep_uuid})

def create_networkInterface():
    print_green("\nCreating Network Interface (NIF)")

    nodes = get_compute_nodes(specificnode, excludenode)

    for i in range(len(nodes)):
        node = nodes[i]
        nif_name = nif_names[i]
        nif_uuid = str(uuid.uuid4())

        nep_data_item = nep_data[i]

        nif_template = template_data["networkInterfaceTemplate"].copy()

        nif_template["metadata"]["namespace"] = ns
        nif_template["metadata"]["name"] = nif_name
        nif_template["metadata"]["uid"] = nif_uuid
        nif_template["metadata"]["ownerReferences"][0]["name"] = nep_data_item["name"]
        
        if do_apply:
            print_green(f"Polling for real UID of NEP {nep_data_item['name']}...")
            # This is done to get the real UID of the NEP created in the previous step, which is needed for the OwnerReference in the NIF. The generated UUID is just a placeholder and will be replaced with the real UID once fetched.
            real_nep_uid = get_k8s_resource_uid("networkendpoint", nep_data_item["name"], ns, timeout=10)
            if real_nep_uid:
                print(f"Fetched real UID for NEP {nep_data_item['name']}: {real_nep_uid}")
                nif_template["metadata"]["ownerReferences"][0]["uid"] = real_nep_uid
            else:
                print_red(f"CRITICAL: Could not fetch real UID for NEP {nep_data_item['name']}. Using generated UUID which might fail validation.")
                nif_template["metadata"]["ownerReferences"][0]["uid"] = nep_data_item["uuid"] # Uses generated UUID, but this may cause validation issues if it doesnt match the real NEP UID.
        else:
            print_yellow(f"Warning: Not applying resources (-a flag missing). Using generated UUID for NEP {nep_data_item['name']}.") 
            print_yellow("The NetworkInterface OwnerReference UID will NOT match the real NEP UID when applied later manually.")
            nif_template["metadata"]["ownerReferences"][0]["uid"] = nep_data_item["uuid"]
        nif_template["metadata"]["labels"]["ResourceID"] = vnic_names[i]
        nif_template["metadata"]["labels"]["OwnerNamespace"] = ns
        nif_template["metadata"]["labels"]["VPCID"] = vpcid
        nif_template["spec"]["vpcid"] = vpcid
        nif_template["spec"]["nodeName"] = node.decode('utf-8')
        
        if vni_type == 'xacc':
            if "virtualNetworkInterface" not in nif_template["spec"]:
                nif_template["spec"]["virtualNetworkInterface"] = {}
            nif_template["spec"]["virtualNetworkInterface"]["Name"] = vni_names[i]
            nif_template["spec"]["virtualNetworkInterface"]["Namespace"] = xacc_namespace
        elif vni_type == 'base' or vni_type == 'cvsi' or vni_type == 'smt':
            nif_template["spec"]["virtualNetworkInterface"] = vni_names[i]
        else:
             if "virtualNetworkInterface" in nif_template["spec"]:
                 del nif_template["spec"]["virtualNetworkInterface"]

        applying(nif_template)

#----------------------------------------------------------------------------------------
#   Resource Function Mappings
#----------------------------------------------------------------------------------------
default_resource_functions = {
    # Default resources
    "Router": create_router,
    "Routing Table": create_routing_table,
    "Ingress Routing Table": create_ingress_routing_table,
    "Security Groups": create_security_groups,
    "Nacls": create_nacls,
    "Networks": create_networks,
    "Foreign Networks": create_foreign_networks,
    "Vnics": create_vnics,
    # Optional EndpointGateway with -epgw flag
    "EndpointGateway": create_endpoint_gateway,
    # Optional Loadbalancers with -lb flag
    "Loadbalancer": create_lb,
    "Lb Pool": create_lb_pool,
    "Lb Listeners": create_lb_listeners,
    "Lb Pool Members": create_lb_pool_members,
    # Optional PublicAddressRange with -parc flag
    "Public Address Range": create_public_address_range,
    # Optional FlowLog with -fl flag
    "FlowLog": create_flowlog
}

all_resource_functions = {
    # Default resources
    "Router": create_router,
    "Cluster VSI": create_clusterVSI,
    "Routing Table": create_routing_table,
    "Ingress Routing Table": create_ingress_routing_table,
    "Security Groups": create_security_groups,
    "Nacls": create_nacls,
    "Networks": create_networks,
    "Foreign Networks": create_foreign_networks,
    # Optional resources with -vni flag
    "ReservedIp": create_reserved_ip,
    "Share Mount Target": create_smt,
    "Virtual Network Interface": create_vni,
    "Vnics": create_vnics,
    # Optional EndpointGateway with -epgw flag
    "EndpointGateway": create_endpoint_gateway,
    # Optional Loadbalancers with -lb flag
    "Loadbalancer": create_lb,
    "Lb Pool": create_lb_pool,
    "Lb Listeners": create_lb_listeners,
    "Lb Pool Members": create_lb_pool_members,
    # Optional PublicAddressRange with -parc flag
    "Public Address Range": create_public_address_range,
    # Optional FlowLog with -fl flag
    "FlowLog": create_flowlog
}

#---------------------------------------------------------------------------------------------------
#   Applying and YAML Writing Functions
#---------------------------------------------------------------------------------------------------
def _initialize_global_vars(routerIndex_arg):
    # Common initialization of global variables
    global rName, rPrefix, vpcid, rtrTableName, ingressRTName, resourceGroup, resourceID, rPrefix, nws, naclName, sgName, router_address_prefixes, local_net_prefixes, foreign_net_prefixes, serviceGatewayIP_address, serviceGatewayIP_range, routerIndex, vnic_names
    
    routerIndex = routerIndex_arg
    rPrefix = "r007"
    rName = f"{rPrefix}-{str(uuid.uuid4())}"
    vpcid = rName
    rtrTableName = f"{rPrefix}-{str(uuid.uuid4())}"
    ingressRTName = f"{rPrefix}-{str(uuid.uuid4())}"
    resourceGroup = "fakedata119e4a61a3a015eb6d44ebbb"
    resourceID = "1e749755-119e-4a61-a3a0-15eb6d44ebbb"
    nws = []
    vnic_names = []
    sgName = ""
    naclName = ""
    router_address_prefixes, local_net_prefixes, foreign_net_prefixes = generate_addressPrefixes(routerIndex, nwcount)
    serviceGatewayIP_address, serviceGatewayIP_range = generate_serviceGatewayIP(routerIndex)

def _write_yaml(saveyaml, yaml_str, template):
    if saveyaml:
        namespace, kind, idName = extract_metadata(template)
        
        folder_name = f"vpc-{routerIndex}-{vpcid[-5:]}"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        
        name_suffix = idName[-5:]
        final_filename = f"{kind.lower()}_{name_suffix}.yaml"
        full_path = os.path.join(folder_name, final_filename)
        
        with open(full_path, "w") as resources_yaml:
            resources_yaml.write(yaml_str)

def _applying(template, applied_resources_file, saveyaml):
    optional_kinds = {"loadbalancer", "lbpool", "lblistener", "lbpoolmember", "publicaddressrange"}
    
    yaml_str = yaml.dump(template, default_flow_style=False)
    namespace, kind, idName = extract_metadata(template)
    
    if not do_apply:
        formatted_string = f"{namespace}, {kind}, {idName} - CREATED YAMLs, NOT APPLIED"
        applied_resources_file.write(formatted_string + "\n")
        
        folder_name = f"vpc-{routerIndex}-{vpcid[-5:]}"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        
        name_suffix = idName[-5:]
        final_filename = f"{kind.lower()}_{name_suffix}.yaml"
        full_path = os.path.join(folder_name, final_filename)
        
        with open(full_path, "w") as resources_yaml:
            resources_yaml.write(yaml_str)
    else:
        kubectl_apply_command = f"kubectl apply -f - <<EOF\n{yaml_str}\nEOF"
        
        # Retry logic for resource creation
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):  # Added to overcome transient issues
            result = apply(kubectl_apply_command, kind)
            if result.returncode == 0:
                break  # Success
            
            print_yellow(f"Attempt {attempt + 1}/{max_retries} failed for resource {kind}/{idName}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

        if result.returncode != 0:
            is_optional = kind.lower() in optional_kinds
            if is_optional:
                print_yellow(f"WARNING: Optional resource '{kind}' with name '{idName}' failed to apply after {max_retries} attempts. Continuing execution.")
            else:
                print_red(f"CRITICAL ERROR: Base resource '{kind}' with name '{idName}' failed to apply after {max_retries} attempts.") # Added to prevent cascading failures
                # Save the failed YAML for debugging before halting
                error_filename = f'error_creating_{kind}_{idName}.yaml'
                print_red(f"Saving failed YAML to {error_filename} for debugging.")
                with open(error_filename, 'w') as error_file:
                    error_file.write(yaml_str)
                print_red("Halting execution.")
                sys.exit(1)

        formatted_string = f"{namespace}, {kind}, {idName}"
        applied_resources_file.write(formatted_string + "\n")
        
        # Only run kubectl_check if the apply command was successful
        if result.returncode == 0:
            kubectl_check(namespace, kind, idName, yaml_str)
        
        _write_yaml(saveyaml, yaml_str, template)
        

#----------------------------------------------------------------------------------------
#  Shell Scripts Creation
#----------------------------------------------------------------------------------------

def create_shell_scripts(vpcid, vni_type, loadbalancer, do_apply, routerIndex, ns):
    if not do_apply:
        folder_name = f"vpc-{routerIndex}-{vpcid[-5:]}"

        print("The resources are \033[91mNOT\033[0m applied, creating the shell scripts to apply/delete")
        # Script to apply all base k8s objects
        apply_basek8s_path = os.path.join(folder_name, "apply_basek8s.sh")
        with open(apply_basek8s_path, "w") as f:
            # Modified to handle both original and numbered filenames
            for filename in os.listdir(folder_name):
                if (filename.startswith("router") or filename.startswith("Router")) and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir(folder_name):
                if (filename.startswith("routingtable") or filename.startswith("RoutingTable")) and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir(folder_name):
                if (filename.startswith("securitygroup") or filename.startswith("SecurityGroup")) and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir(folder_name):
                if (filename.startswith("networkacl") or filename.startswith("NetworkACL")) and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir(folder_name):
                if (filename.startswith("flowlog") or filename.startswith("FlowLog")) and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir(folder_name):
                if (filename.startswith("network") or filename.startswith("Network")) and filename.endswith(".yaml") and "networkacl" not in filename.lower() and "interface" not in filename.lower() and "endpoint" not in filename.lower():
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")

        os.chmod(apply_basek8s_path, 0o755)

        # CLEANUP SCRIPT
        cleanup_script_path = os.path.join(folder_name, "cleanup.sh")
        cleanup_script_content = f"""\
kinds=(virtualnic networkinterface networkendpoint endpointgateway lbpoolmember lblistener lbpool loadbalancer virtualnetworkinterface sharemounttarget reservedip ipaddress network securitygroup networkacl routingtable clusternetwork publicaddressrange router)
for kind in ${{kinds[@]}}; do
  echo "deleting "$kind"s"
  for obj in $(kubectl -n {ns} get $kind | grep -v NAME | awk '{{ print $1 }}') ; do
    echo $obj
    kubectl -n {ns} delete $kind $obj
  done
done
"""
        with open(cleanup_script_path, "w") as file:
            file.write(cleanup_script_content)
        os.chmod(cleanup_script_path, 0o755)

        # Script to apply all the VNIC files
        apply_vnic_path = os.path.join(folder_name, "apply_vnic.sh")
        with open(apply_vnic_path, "w") as f:
            for filename in os.listdir(folder_name):
                if filename.startswith("VirtualNic") or filename.startswith("virtualnic") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
        os.chmod(apply_vnic_path, 0o755)

        # Script to delete all the VNICs
        delete_vnic_path = os.path.join(folder_name, "delete_vnic.sh")
        with open(delete_vnic_path, "w") as f:
            for filename in os.listdir(folder_name):
                if filename.startswith("VirtualNic") or filename.startswith("virtualnic") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl delete -f {filename}\n")
        os.chmod(delete_vnic_path, 0o755)

        if vni_type == 'cvsi':
            apply_cvsi_path = os.path.join(folder_name, "apply_cvsi.sh")
            with open(apply_cvsi_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("ClusterNetwork") or filename.startswith("clusternetwork") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_cvsi_path, 0o755)

            delete_cvsi_path = os.path.join(folder_name, "delete_cvsi.sh")
            with open(delete_cvsi_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("ClusterNetwork") or filename.startswith("clusternetwork") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
            os.chmod(delete_cvsi_path, 0o755)

        # Script to apply all the VNI and RIPs
        if vni_type in ['smt', 'cvsi']:
            apply_vni_path = os.path.join(folder_name, "apply_vni.sh")
            with open(apply_vni_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("VirtualNetworkInterface") or filename.startswith("virtualnetworkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_vni_path, 0o755)

            apply_rip_path = os.path.join(folder_name, "apply_rip.sh")
            with open(apply_rip_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("ReservedIP") or filename.startswith("reservedip") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_rip_path, 0o755)

            apply_smt_path = os.path.join(folder_name, "apply_smt.sh")
            with open(apply_smt_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("ShareMountTarget") or filename.startswith("sharemounttarget") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_smt_path, 0o755)

            apply_vniresources_path = os.path.join(folder_name, "apply_vniresources.sh")
            with open(apply_vniresources_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("ReservedIP") or filename.startswith("reservedip") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("ShareMountTarget") or filename.startswith("sharemounttarget") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("VirtualNetworkInterface") or filename.startswith("virtualnetworkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_vniresources_path, 0o755)

            delete_vniresources_path = os.path.join(folder_name, "delete_vniresources.sh")
            with open(delete_vniresources_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("VirtualNetworkInterface") or filename.startswith("virtualnetworkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("ShareMountTarget") or filename.startswith("sharemounttarget") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("ReservedIP") or filename.startswith("reservedip") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
            os.chmod(delete_vniresources_path, 0o755)

        if vni_type == 'xacc':
            apply_xacc_path = os.path.join(folder_name, "apply_x-acc_VNIresources.sh")
            with open(apply_xacc_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("ReservedIP") or filename.startswith("reservedip") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("NetworkInterface") or filename.startswith("networkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("NetworkEndpoint") or filename.startswith("networkendpoint") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("VirtualNetworkInterface") or filename.startswith("virtualnetworkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_xacc_path, 0o755)

            delete_xacc_path = os.path.join(folder_name, "delete_x-acc_VNIresources.sh")
            with open(delete_xacc_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.startswith("VirtualNetworkInterface") or filename.startswith("virtualnetworkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("NetworkInterface") or filename.startswith("networkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("NetworkEndpoint") or filename.startswith("networkendpoint") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("ReservedIP") or filename.startswith("reservedip") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
            os.chmod(delete_xacc_path, 0o755)

        # Script to Apply all the lb
        if loadbalancer == 'yes':
            apply_lb_path = os.path.join(folder_name, "apply_lb.sh")
            with open(apply_lb_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LBPoolMember") or filename.startswith("lbpoolmember")) and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LBListener") or filename.startswith("lblistener")) and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LBPool") or filename.startswith("lbpool")) and filename.endswith(".yaml") and "member" not in filename.lower():
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LoadBalancer") or filename.startswith("loadbalancer")) and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_lb_path, 0o755)

            # Script to delete all the lb
            delete_lb_path = os.path.join(folder_name, "delete_lb.sh")
            with open(delete_lb_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LBPoolMember") or filename.startswith("lbpoolmember")) and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LBListener") or filename.startswith("lblistener")) and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LBPool") or filename.startswith("lbpool")) and filename.endswith(".yaml") and "member" not in filename.lower():
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if (filename.startswith("LoadBalancer") or filename.startswith("loadbalancer")) and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
            os.chmod(delete_lb_path, 0o755)

        # Script to Apply NEP/NIF if present
        if nep_nif:
            apply_nep_nif_path = os.path.join(folder_name, "apply_nep_nif.sh")
            with open(apply_nep_nif_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.lower().startswith("networkendpoint") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if filename.lower().startswith("networkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
            os.chmod(apply_nep_nif_path, 0o755)

            delete_nep_nif_path = os.path.join(folder_name, "delete_nep_nif.sh")
            with open(delete_nep_nif_path, "w") as f:
                for filename in os.listdir(folder_name):
                    if filename.lower().startswith("networkinterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir(folder_name):
                    if filename.lower().startswith("networkendpoint") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
            os.chmod(delete_nep_nif_path, 0o755)

        # Print Test Files created
        yaml_files = sorted([file for file in os.listdir(folder_name) if file.endswith('.yaml')])
        yaml_count = len(yaml_files)
        print("Test Files created: \n", " ".join(yaml_files), f"\n(Total: {yaml_count})")

        # Print scripts created
        sh_files = sorted([file for file in os.listdir(folder_name) if file.endswith('.sh')])
        sh_count = len(sh_files)
        print("Scripts created: \n", " ".join(sh_files), f"\n(Total: {sh_count})")

        
# ----------------------------------------------------------------------------------------
#   APPLY FUNCTIONS
# ----------------------------------------------------------------------------------------

def applyResources(saveyaml, routerIndex):
    _initialize_global_vars(routerIndex)
    print(f"\nnwcount: {nwcount}, epcount: {epcount}, ns: {ns}, mz: {mz}\n")
    
    applied_resources_file = open("applied_resources.txt", "a")
    applied_resources_file.write("\n")
    
    global applying
    def applying(template):
        _applying(template, applied_resources_file, saveyaml)
    
    for resource, func in default_resource_functions.items():
        func()
    
    applied_resources_file.close()
    print("------- The resources in this SET are applied  -------")
    create_shell_scripts(vpcid, vni_type, loadbalancer, do_apply, routerIndex, ns)

def applyallresources(saveyaml, routerIndex):
    _initialize_global_vars(routerIndex)
    print(f"\nnwcount: {nwcount}, epcount: {epcount}, ns: {ns}, mz: {mz}\n")
    
    applied_resources_file = open("applied_resources.txt", "a")
    applied_resources_file.write("\n")
    
    global applying
    def applying(template):
        _applying(template, applied_resources_file, saveyaml)
    
    for resource, func in all_resource_functions.items():
        func()
    
    applied_resources_file.close()
    print("------- The resources in this SET are applied  -------")
    create_shell_scripts(vpcid, vni_type, loadbalancer, do_apply, routerIndex, ns)



def applySpecificResource(resource_type):

    #Setting the variables as global for access
    global rName, rPrefix, vpcid, rtrTableName, ingressRTName, resourceGroup, resourceID, rPrefix, nws, naclName, sgName

    rPrefix = "r007"
    rName = f"{rPrefix}-{str(uuid.uuid4())}"
    vpcid = rName
    sgName = ""
    naclName = ""
    rtrTableName = f"{rPrefix}-{str(uuid.uuid4())}"
    ingressRTName = f"{rPrefix}-{str(uuid.uuid4())}"
    resourceGroup = "fakedata119e4a61a3a015eb6d44ebbb"
    resourceID = "1e749755-119e-4a61-a3a0-15eb6d44ebbb"
    nws = []

    #Opening the file to track the applied resources along with namespace
    applied_resources_file = open("applied_resources.txt", "a")
    applied_resources_file.write("\n")


    global applying

    def applying(template):
        print("Aplying Specific resource (Called by the MANIPULATION Action)")
        yaml_str = yaml.dump(template, default_flow_style=False)
        kubectl_apply_command = f"kubectl apply -f - <<EOF\n{yaml_str}\nEOF"
        namespace, kind, idName = extract_metadata(template)
        apply(kubectl_apply_command, kind)
        formatted_string = f"{namespace}, {kind}, {idName}"
        applied_resources_file.write(formatted_string + "\n")
        kubectl_check(namespace, kind, idName, yaml_str)

    all_resource_functions[resource_type]()

    applied_resources_file.close()


#----------------------------------------PARALLEL APPLY-------------------------------------------------------
def apply_vpc_worker(vpc_dir_path):
    # Worker function for multiprocessing with retry logic.
    apply_command = f"kubectl apply -f {vpc_dir_path}"
    max_retries = 3
    retry_interval = 3  # seconds

    for attempt in range(max_retries):
        result = subprocess.run(apply_command, capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            # Return success status and the directory path
            return (True, vpc_dir_path, result.stdout)
        
        # If failed, and it's not the last attempt, wait and retry
        if attempt < max_retries - 1:
            vpc_name = os.path.basename(vpc_dir_path)
            print_yellow(f"[WORKER - {vpc_name}] Attempt {attempt + 1}/{max_retries} failed. Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
        else:
            # This was the last attempt, so return the failure
            return (False, vpc_dir_path, result.stderr)

def parallelApplyResources(namespace, args, start_index, end_index):
    # Validate CPU count
    cpu_check(args)
    
    # --- Setup and Load Globals ---
    setup_and_load_globals(namespace, args)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    parallel_run_dir = f"parallel_run_{timestamp}"
    os.makedirs(parallel_run_dir)
    print_green(f"Starting new parallel run. YAMLs will be generated in '{parallel_run_dir}'")
    
    vpc_dirs_to_apply = []
    start_time_gen = time.time()

    # --- 1. Generation Phase (Sequential) ---
    print_green(f"Generating YAML files for {args.sets} VPC(s)...")
    for i in range(start_index, end_index + 1):
        global routerIndex, vpcid
        routerIndex = i
        
        _initialize_global_vars(routerIndex)
        
        vpc_dir_name = f"vpc-{routerIndex}-{vpcid[-5:]}"
        vpc_dir_path = os.path.join(parallel_run_dir, vpc_dir_name)
        os.makedirs(vpc_dir_path)
        
        print(f"  -> Generating for VPC {routerIndex} in {vpc_dir_path}")

        # Temporarily override the 'applying' function to only generate YAML files
        global applying
        def generate_yaml_only(template):
            yaml_str = yaml.dump(template, default_flow_style=False)
            ns, kind, idName = extract_metadata(template)
            
            # Write metadata to a per-VPC file for later collection.
            with open(os.path.join(vpc_dir_path, "resources.txt"), "a") as f:
                f.write(f"{ns}, {kind}, {idName}\n")

            # Creation order comes from utils.py
            prefix = creation_order.get(kind, "99") # defaulting to '99' for any unlisted kinds
            
            final_filename = f"{prefix}_{kind.lower()}_{idName}.yaml"
            full_path = os.path.join(vpc_dir_path, final_filename)
            with open(full_path, "w") as f:
                f.write(yaml_str)
        
        applying = generate_yaml_only
        
        # Call the main resource creation logic
        resource_functions = all_resource_functions if vni_type is not None else default_resource_functions
        for resource, func in resource_functions.items():
            func()
            
        vpc_dirs_to_apply.append(vpc_dir_path)
    
    gen_time = time.time() - start_time_gen
    print_green(f"YAML generation complete for all {setCount} VPCs in {gen_time:.2f} seconds.")

    # --- 2. Application Phase (Parallel) ---
    worker_count = args.parallel
    print_green(f"\nApplying resources in parallel using {worker_count} workers...")
    
    start_time_apply = time.time()
    successful_vpcs = []
    failed_vpcs = []

    with multiprocessing.Pool(processes=worker_count) as pool, open("applied_resources.txt", "a") as main_resources_file:
        # Use imap_unordered to get results as they complete
        results_iterator = pool.imap_unordered(apply_vpc_worker, vpc_dirs_to_apply)
        
        for success, dir_path, output in results_iterator:
            vpc_name = os.path.basename(dir_path)
            if success:
                print_green(f"[SUCCESS] Applied {vpc_name}")
                successful_vpcs.append(dir_path)
                
                # On success, append the per-VPC resources file to the main one.
                try:
                    with open(os.path.join(dir_path, "resources.txt"), "r") as vpc_resources_file:
                        main_resources_file.write(vpc_resources_file.read())
                except FileNotFoundError:
                    print_yellow(f"Warning: Could not find resources.txt for successfully applied VPC {vpc_name}.")

            else:
                print_red(f"[FAILURE] Failed to apply {vpc_name}. See parallel_summary.txt for details.")
                failed_vpcs.append((dir_path, output))

    apply_time = time.time() - start_time_apply
    print_green(f"\nParallel application complete in {apply_time:.2f} seconds.")
    
    # --- 3. Summary Generation ---
    summary_filename = "parallel_summary.txt"
    print_green(f"Writing run summary to {summary_filename}...")
    with open(summary_filename, "w") as f:
        f.write(f"--- Parallel Run Summary ---\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("-" * 30 + "\n\n")
        
        f.write(f"Total VPCs Attempted: {len(vpc_dirs_to_apply)}\n")
        f.write(f"Successful:           {len(successful_vpcs)}\n")
        f.write(f"Failed:               {len(failed_vpcs)}\n\n")

        if failed_vpcs:
            f.write("--- Failure Details ---\n")
            for dir_path, error_output in failed_vpcs:
                f.write(f"\nVPC Directory: {os.path.basename(dir_path)}\n")
                f.write("Error Output:\n")
                f.write("="*15 + "\n")
                f.write(error_output)
                f.write("\n" + "="*15 + "\n")
            f.write("\n")

        if successful_vpcs:
            f.write("--- Successful VPCs ---\n")
            for dir_path in successful_vpcs:
                f.write(f"- {os.path.basename(dir_path)}\n")

    print_green("Summary file written.")

    # --- 4. Console Summary ---
    print_green("\n--- Run Summary ---")
    print_green(f"Total VPCs:      {len(vpc_dirs_to_apply)}")
    print_green(f"Successful:      {len(successful_vpcs)}")
    print_red(f"Failed:          {len(failed_vpcs)}")
    print_green(f"Total Time:      {(gen_time + apply_time):.2f} seconds")
    if failed_vpcs:
        print_yellow(f"Review failed VPCs in {summary_filename}")
    print_green("---------------------")


#----------------------------------------BATCH APPLY--------------------------------------------------------
def batchApplyResources(namespace, args, start_index, end_index):
    setup_and_load_globals(namespace, args)
    
    # Main batch run directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_run_dir = f"batch_run_{timestamp}"
    os.makedirs(batch_run_dir)
    print_green(f"Starting new batch run. Output will be saved in '{batch_run_dir}'")
    
    start_time = time.time()
    for i in range(start_index, end_index + 1):
        global routerIndex, vpcid
        routerIndex = i
        print(f"\n--- [VPC {routerIndex}/{setCount}] ---")
        
        _initialize_global_vars(routerIndex)
        
        vpc_dir_name = f"vpc-{routerIndex}-{vpcid[-5:]}"
        vpc_dir_path = os.path.join(batch_run_dir, vpc_dir_name)
        os.makedirs(vpc_dir_path)
        print_green(f"Generating YAML files into '{vpc_dir_path}'...")

        def generate_yaml_only(template):
            yaml_str = yaml.dump(template, default_flow_style=False)
            ns, kind, idName = extract_metadata(template)
            print(f"      -> Generating: {kind} {idName}")
            # Creation order comes from utils.py
            prefix = creation_order.get(kind, "99") # defaulting to '99' for any unlisted kinds
            final_filename = f"{prefix}_{kind.lower()}_{idName}.yaml"
            full_path = os.path.join(vpc_dir_path, final_filename)
            with open(full_path, "w") as f:
                f.write(yaml_str)

        global applying
        applying = generate_yaml_only # Override applying to only generate YAML files for batchApplication
        
        resource_functions = all_resource_functions if vni_type is not None else default_resource_functions
        for resource, func in resource_functions.items():
            func()

        print_yellow(f"Applying all resources from '{vpc_dir_path}'...")
        
        max_retries = 3
        retry_delay = 5  # seconds
        success = False
        for attempt in range(max_retries):
            # Using a list of arguments is safer than shell=True
            apply_command = ["kubectl", "apply", "-f", vpc_dir_path]
            result = subprocess.run(apply_command, capture_output=True, text=True)
            
            # Print kubectl output, colorizing successes and failures
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if "created" in line or "configured" in line:
                        print_green(line)
                    else:
                        print(line)

            if result.returncode == 0:
                success = True
                print_green(f"[VPC {routerIndex}/{setCount}] Batch apply successful.")
                break  # Success, exit the retry loop
            
            # If we are here, the command failed
            print_red(f"\nAttempt {attempt + 1}/{max_retries} failed for VPC {routerIndex}. Error:")
            if result.stderr:
                print_red(result.stderr)

            if attempt < max_retries - 1:
                print_yellow(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        if not success:
            error_message = f"CRITICAL: Batch apply failed for VPC {routerIndex} after {max_retries} attempts. Halting."
            print_red(error_message)
            raise RuntimeError(error_message)

    print("\n-------      ALL BATCH OPERATIONS ARE APPLIED        -------")
    time_taken(start_time, setCount)



#----------------------------------------FULLY PARALLEL CREATION-------------------------------------------------------

def generate_yamls_for_one_vpc(worker_args):
   
    routerIndex, parallel_run_dir, vni_type, args = worker_args
    
    _initialize_global_vars(routerIndex)
    
    vpc_dir_name = f"vpc-{routerIndex}-{vpcid[-5:]}"
    vpc_dir_path = os.path.join(parallel_run_dir, vpc_dir_name)
    os.makedirs(vpc_dir_path)
    
    print(f"  -> Generating YAMLs for VPC #{routerIndex} in directory {vpc_dir_path}")

    def generate_yaml_only(template):
        yaml_str = yaml.dump(template, default_flow_style=False)
        ns, kind, idName = extract_metadata(template)
        
        with open(os.path.join(vpc_dir_path, "resources.txt"), "a") as f:
            f.write(f"{ns}, {kind}, {idName}\n")

        prefix = creation_order.get(kind, "99")
        
        final_filename = f"{prefix}_{kind.lower()}_{idName}.yaml"
        full_path = os.path.join(vpc_dir_path, final_filename)
        with open(full_path, "w") as f:
            f.write(yaml_str)
    
    global applying
    applying = generate_yaml_only
    
    resource_functions = all_resource_functions if vni_type is not None else default_resource_functions
    
    for resource, func in resource_functions.items():
        func()
        
    return vpc_dir_path

def fullyParallelResourceCreation(namespace, args, start_index, end_index):
    if args.fullyparallel is None:
        print_red("Error: The fully parallel mode requires the --fully-parallel ('-fp') flag to be set.")
        sys.exit(1)
        
    # Validate CPU count
    cpu_check(args)

    setup_and_load_globals(namespace, args)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    parallel_run_dir = f"fully_parallel_run_{timestamp}"
    os.makedirs(parallel_run_dir)
    print_green(f"Starting new fully parallel run. YAMLs will be generated in '{parallel_run_dir}'")
    
    worker_count = args.fullyparallel
    print_green(f"PHASE 1: Generating YAML files for {args.sets} VPC(s) in parallel using {worker_count} workers...")
    
    start_time_gen = time.time()
    
    # Create the list of "work packages". Each package has the unique routerIndex for one VPC.
    work_packages = [(i, parallel_run_dir, vni_type, args) for i in range(start_index, end_index + 1)]
    
    with multiprocessing.Pool(processes=worker_count) as pool:
        list_of_vpc_dirs = pool.map(generate_yamls_for_one_vpc, work_packages)
        
    gen_time = time.time() - start_time_gen
    print_green(f"PHASE 1 complete. YAML generation for all {setCount} VPCs finished in {gen_time:.2f} seconds.")

    print_green(f"\nPHASE 2: Applying generated resources to the cluster in parallel using {worker_count} workers...")
    
    start_time_apply = time.time()
    successful_vpcs = []
    failed_vpcs = []

    with multiprocessing.Pool(processes=worker_count) as pool, open("applied_resources.txt", "a") as main_resources_file:
        results_iterator = pool.imap_unordered(apply_vpc_worker, list_of_vpc_dirs)
        
        for success, dir_path, output in results_iterator:
            vpc_name = os.path.basename(dir_path)
            if success:
                print_green(f"[SUCCESS] Applied {vpc_name}")
                successful_vpcs.append(dir_path)
                
                try:
                    with open(os.path.join(dir_path, "resources.txt"), "r") as vpc_resources_file:
                        main_resources_file.write(vpc_resources_file.read())
                except FileNotFoundError:
                    print_yellow(f"Warning: Could not find resources.txt for successfully applied VPC {vpc_name}.")

            else:
                print_red(f"[FAILURE] Failed to apply {vpc_name}. See fully_parallel_summary.txt for details.")
                failed_vpcs.append((dir_path, output))

    apply_time = time.time() - start_time_apply
    print_green(f"PHASE 2 complete. Parallel application finished in {apply_time:.2f} seconds.")
    
    summary_filename = "fully_parallel_summary.txt"
    print_green(f"Writing run summary to {summary_filename}...")
    with open(summary_filename, "w") as f:
        f.write(f"--- Fully Parallel Run Summary ---\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("-" * 30 + "\n\n")
        
        f.write(f"Total VPCs Attempted: {len(list_of_vpc_dirs)}\n")
        f.write(f"Successful:           {len(successful_vpcs)}\n")
        f.write(f"Failed:               {len(failed_vpcs)}\n\n")

        if failed_vpcs:
            f.write("--- Failure Details ---\n")
            for dir_path, error_output in failed_vpcs:
                f.write(f"\nVPC Directory: {os.path.basename(dir_path)}\n")
                f.write("Error Output:\n")
                f.write("="*15 + "\n")
                f.write(error_output)
                f.write("\n" + "="*15 + "\n")
            f.write("\n")

        if successful_vpcs:
            f.write("--- Successful VPCs ---\n")
            for dir_path in successful_vpcs:
                f.write(f"- {os.path.basename(dir_path)}\n")

    print_green("Summary file written.")

    print_green("\n--- Run Summary ---")
    print_green(f"Total VPCs:      {len(list_of_vpc_dirs)}")
    print_green(f"Successful:      {len(successful_vpcs)}")
    print_red(f"Failed:          {len(failed_vpcs)}")
    print_green(f"Total Time:      {(gen_time + apply_time):.2f} seconds")
    if failed_vpcs:
        print_yellow(f"Review failed VPCs in {summary_filename}")
    print_green("---------------------")


#----------------------------------------APPLY--------------------------------------------------------
def setup_and_load_globals(namespace, args):
    env = args.environment
    
    global mz, setCount, routerIndex, loadbalancer, epgwcount, nwcount, epcount, ripcount, ns, saveyaml, do_apply, specificnode, excludenode, vni_type, parcount, xacc_namespace, nep_nif, flowlog_kind, flowlog_count, flowlog_one, included_protocols, excluded_protocols

    routerIndex = 0

    try:
        if env == "region-1":
            region_file = "/etc/sim/region"
            region_contents = subprocess.check_output(["cat", region_file]).decode('utf-8')
            mz_match = re.search(r'zone([\da-z]+)\b', region_contents)
            if mz_match:
                mz = mz_match.group(1)
            else:
                print("Error: ZONE value not found in", region_file)
                sys.exit(1)
        elif env == "region-2":
            region_file = "/etc/sim/region"
            region_contents = subprocess.check_output(["cat", region_file]).decode('utf-8')
            mz = ''.join(re.findall(r'\d+', region_contents))
        else:
            print("Please specify the environment as 'region-1' or 'region-2'")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print_red(f"Could not fetch the ZONE value: {e.output.decode('utf-8')}")
        usr_mz_input = input("So please enter the ZONE value (4 digit alphanumeric): ")
        mz = str(usr_mz_input)

    mz = mz[:4]
    if len(mz) < 4:
        mz = "0" + mz

    print(f"The set ZONE value is: {mz}")
    mz = mz[:4]

    ns = namespace  # Namespace for resource creation
    setCount = args.sets  # Number of VPCs to create
    nwcount = args.networkcount  # Number of networks to create per VPC
    epcount = args.endpointcount  # Number of endpoints to create per VNIC
    ripcount = args.ripcount  # Number of reserved IPs to create
    saveyaml = args.saveyaml  # Whether to save resources as YAML files
    do_apply = args.apply  # This will directly apply the resources instead of saving them in YAML format
    specificnode = args.specificnode  # Specific node to create VNIC resources on
    excludenode = args.excludenode  # Node to exclude from VNIC creation
    vni_type = args.vnitype  # This will be None, 'smt', 'cvsi', 'xacc', or 'base'
    parcount = args.parcount # This will create PAR resource
    xacc_namespace = args.xacc_namespace # Namespace for cross-account VNI, default is 'xacc-ns'
    nep_nif = args.nep_nif # Flag to create NEP and NIF directly
    flowlog_one = args.flowlog_one # Flag to limit flowlog creation to 1 instance
    included_protocols = args.included_protocols # List of included protocols
    excluded_protocols = args.excluded_protocols # List of excluded protocols
    
    # Parsing FlowLog inputs to match any cases, ease of use.
    flowlog_kind = None
    kind_map = {
        'router': 'Router',
        'network': 'Network',
        'virtualnic': 'VirtualNic', 'vnic': 'VirtualNic',
        'virtualnetworkinterface': 'VirtualNetworkInterface', 'vni': 'VirtualNetworkInterface'
    }
    
    if args.flowlogs:
        user_input = args.flowlogs.lower()
        if user_input in kind_map:
            flowlog_kind = kind_map[user_input]
        else:
            valid_options = sorted(list(set(kind_map.keys())))
            print_red(f"Error: '{args.flowlogs}' is not a valid FlowLog target. Valid options: {', '.join(valid_options)}.")
            sys.exit(1)


    # Flag to apply the LoadBalancers or not
    loadbalancer = "yes" if args.loadbalancer else "no"
    epgwcount = args.epgwcount

    # LOADING TEMPLATE DATA
    global template_data
    def load_template_data():
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        template_path = os.path.join(script_dir, "template.json")
        try:
            with open(template_path, "r") as json_file:
                return json.load(json_file)
        except FileNotFoundError:
            print("Template Data not found / path not configured properly. Please correct it before proceeding")
            sys.exit(1)

    # Load the template data
    template_data = load_template_data()

    # Preflight checks
    if not shutil.which("kubectl"):
        print_red("kubectl is not installed or not in your PATH. This script requires kubectl to function.")
        sys.exit(1)
    if int(epcount) > 255:
        print_red("Endpoint count cannot be greater than 255, Restart the script with a lower value.")
        sys.exit(1)
    if specificnode and excludenode:
        print_red("The --specificnode (-sn) and --excludenode (-en) flags are mutually exclusive. Please use only one.")
        sys.exit(1)
    if ('-ripc' in sys.argv or '--reservedipcount' in sys.argv) and vni_type is None:
        print_red("The --reservedipcount (-ripc) flag requires a VNI type to be specified with the -vni flag.")
        sys.exit(1)

# MAIN function to create resources
# This function sets up the environment, loads templates, and calls resource creation functions
#-----------------------------------------------------------------------------------------------------
def create_resources(namespace, args, specificResource=None):
    if args.action.lower() not in ['create', 'c', 'manipulate', 'm']:
        print(f"Invalid action.. {args.action}")
        return

    # Removed VNICs from function map, just for direct NIF and NEP creation.
    if args.nep_nif:
        print_green("\n*** NEP/NIF Mode Enabled: Swapping VNICs for NEP+NIF ***")
        
        if "Vnics" in default_resource_functions: del default_resource_functions["Vnics"]
        default_resource_functions["Network Endpoint"] = create_networkEndpoint
        default_resource_functions["Network Interface"] = create_networkInterface

        if "Vnics" in all_resource_functions: del all_resource_functions["Vnics"]
        all_resource_functions["Network Endpoint"] = create_networkEndpoint
        all_resource_functions["Network Interface"] = create_networkInterface

    if args.action.lower() in ['manipulate', 'm']:
        if specificResource:
            applySpecificResource(specificResource)
        return

    # --- STATE MANAGEMENT LOGIC (Centralized) ---
    STATE_FILE = ".nrs_state_file.txt"
    last_index = 0
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    last_index = int(content)
        except (IOError, ValueError) as e:
            print_yellow(f"Warning: Could not read or parse state file '{STATE_FILE}'. Starting from index 1. Error: {e}")
            last_index = 0
    
    start_index = last_index + 1
    end_index = last_index + args.sets

    # --- Main Actions ---
    if args.batchapply:
        batchApplyResources(namespace, args, start_index, end_index)
    elif args.parallel:
        parallelApplyResources(namespace, args, start_index, end_index)
    elif args.fullyparallel:
        fullyParallelResourceCreation(namespace, args, start_index, end_index)
    else:
        # --- Default to Sequential Apply ---
        setup_and_load_globals(namespace, args)
        start_time = time.time()
        
        resource_creation_func = applyallresources if vni_type is not None else applyResources
        
        for routerIndex in range(start_index, end_index + 1):
            print_green(f"--------  Creating VPC (ID: {routerIndex}) / {args.sets} --------")
            resource_creation_func(saveyaml, routerIndex)
        
        if do_apply:
            print("-------      ALL THE RESOURCES ARE APPLIED        -------")
            time_taken(start_time, args.sets)

    # --- Update State File (runs for all modes) ---
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(end_index))
        print_green(f"State file '{STATE_FILE}' updated with last index: {end_index}")
    except IOError as e:
        print_red(f"CRITICAL: Failed to write to state file '{STATE_FILE}'. Future runs may have IP conflicts. Error: {e}")


# --------------------------------------APPLY DONE --------------------------------------


# ----------------------------------------------------------------------------------------
#   GET / DESCRIBE / DELETE FUNCTIONS
# ----------------------------------------------------------------------------------------
def get_resources(namespace):
    kinds = K8S_RESOURCE_KINDS
    ns = namespace
    all_resources = []
    total_resource_count = 0
    
    print_yellow(f"Checking resources in the '{ns}' namespace...")

    for kind in kinds:
        command = f"kubectl get {kind} -n {ns} --no-headers --ignore-not-found=true -o custom-columns=:metadata.name 2>/dev/null"
        try:
            resources = subprocess.check_output(command, shell=True, universal_newlines=True).strip().split('\n')
            if resources and resources[0]:
                all_resources.append((kind, resources))
                total_resource_count += len(resources)
        except subprocess.CalledProcessError:
            continue

    if not all_resources:
        print_green("No resources found in this namespace.")
        return

    print_green("\nThe following resources were found:")
    print_green("+---------------------------+---------+")
    print_green(f"| {'Resource Kind':<25} | {'Count':<7} |")
    print_green("+---------------------------+---------+")
    for kind, resources in all_resources:
        print_green(f"| {kind:<25} | {len(resources):<7} |")
    print_green("+---------------------------+---------+")
    print_green(f"| {'Total':<25} | {total_resource_count:<7} |")
    print_green("+---------------------------+---------+")

    list_all = False
    if total_resource_count <= 70:
        list_all = True
    else:
        try:
            confirm = input("\nDo you want to list all of them? (y/n): ").lower()
            if confirm in ['y', 'yes']:
                list_all = True
        except KeyboardInterrupt:
            print_yellow("\n\nAborting.")
            return

    if list_all:
        print_green(f"\nRunning 'Kubectl get' in namespace '{ns.capitalize()}': \n")
        for kind, resources in all_resources:
            print_green(f"\nFound {len(resources)} {kind}s: ")
            for resource_name in resources:
                print(resource_name)
    elif total_resource_count > 70:
        print_yellow("Aborting.")


def get_resource_status(namespace, user_input):
    # --- Handling a resource NAME ---
    if any(char.isdigit() for char in user_input):
        print_green(f"Input '{user_input}', Treating it as a resource name.")
        resource_name = user_input
        resource_found = False

        kinds = K8S_RESOURCE_KINDS

        for kind in kinds:
            # Try to get the resource by name and kind
            command = f"kubectl get {kind} {resource_name} -n {namespace}"
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

            if result.returncode == 0:
                resource_found = True
                print_green(f"Found resource '{resource_name}' with kind '{kind}'.")

                command_get_yaml = f"kubectl get {kind} {resource_name} -n {namespace} -o yaml"
                result = run_command(command_get_yaml)

                if result:
                    try:
                        resource_yaml = yaml.safe_load(result)
                        if 'status' in resource_yaml and resource_yaml['status']:
                            # Use yaml.dump for pretty printing
                            print(yaml.dump(resource_yaml['status'], default_flow_style=False, indent=2))
                        else:
                            print_yellow("No 'status' field found or status is empty for this resource.\n")
                    except yaml.YAMLError as e:
                        print_red(f"Error parsing YAML for {kind} '{resource_name}': {e}\n")
                else:
                    print_red(f"Failed to get YAML for {kind} '{resource_name}'.\n")
                break

        if not resource_found:
            print_red(f"Error: Could not find any resource with the name '{resource_name}' in namespace '{namespace}'.")

    else:
        # --- Handling a resource KIND ---
        user_kind_input = user_input
        print_green(f"Input '{user_kind_input}', Treating it as a resource kind.")
        
        kinds = K8S_RESOURCE_KINDS

        ns = namespace

        # Find the closest match for the user input
        kind = difflib.get_close_matches(user_kind_input, kinds, n=1, cutoff=0.1)
        kind = kind[0] if kind else None

        if kind:
            print_green(f"Fetching status for '{kind}' resources in namespace '{ns}':\n")

            command_names = f"kubectl -n {ns} get {kind} --no-headers -o custom-columns=:metadata.name"
            resource_names_output = run_command(command_names)

            if resource_names_output:
                resource_names = resource_names_output.decode('utf-8').strip().splitlines()
                
                if not resource_names or (len(resource_names) == 1 and not resource_names[0]):
                    print_yellow(f"No '{kind}' resources found in namespace '{ns}'.")
                    return

                print_green(f"Found {len(resource_names)} {kind}(s): {', '.join(resource_names)}\n")

                for resource_name in resource_names:
                    print_green(f"--- Status for {kind}/{resource_name} ---")
                    command_get_yaml = f"kubectl -n {ns} get {kind} {resource_name} -o yaml"
                    result = run_command(command_get_yaml)

                    if result:
                        try:
                            resource_yaml = yaml.safe_load(result)
                            if 'status' in resource_yaml and resource_yaml['status']:
                                # Use yaml.dump for pretty printing
                                print(yaml.dump(resource_yaml['status'], default_flow_style=False, indent=2))
                            else:
                                print_yellow("No 'status' field found or status is empty for this resource.\n")
                        except yaml.YAMLError as e:
                            print_red(f"Error parsing YAML for {kind} '{resource_name}': {e}\n")
                    else:
                        print_red(f"Failed to get YAML for {kind} '{resource_name}'.\n")
            else:
                print_yellow(f"No '{kind}' resources found in namespace '{ns}'.")
        else:
            print_red(f"Error: No resource match found for '{user_kind_input}'.")
            print_yellow(f"Available resource types are: {', '.join(kinds)}")

def describe_resources(namespace, user_input):
    if any(char.isdigit() for char in user_input):
        print_green(f"Input '{user_input}': Treating it as a resource name.")
        resource_name = user_input
        resource_found = False

        kinds = K8S_RESOURCE_KINDS

        for kind in kinds:
            command = f"kubectl get {kind} {resource_name} -n {namespace}"
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

            if result.returncode == 0:
                resource_found = True
                print_green(f"Found resource '{resource_name}' with kind '{kind}'.")

                command_describe = f"kubectl describe {kind} {resource_name} -n {namespace}"
                result = run_command(command_describe)
                print(result.decode('utf-8'))
                break

        if not resource_found:
            print_red(f"Error: Could not find any resource with the name '{resource_name}' in namespace '{namespace}'.")

    else:
        user_kind_input = user_input
        kinds = K8S_RESOURCE_KINDS

        # Find the closest match for the user input
        kind = difflib.get_close_matches(user_kind_input, kinds, n=1, cutoff=0.1)
        kind = kind[0] if kind else None

        if kind:
            ns = namespace
            print_green(f"Running 'kubectl describe {kind}' in namespace '{ns}':\n")

            command_names = f"kubectl -n {ns} get {kind} --no-headers -o custom-columns=:metadata.name"
            resource_names = run_command(command_names)

            if resource_names:
                resource_names = resource_names.decode('utf-8').splitlines()
                print_green(f"\nFound {len(resource_names)} {kind}(s): {', '.join(resource_names)}\n")

                for resource_name in resource_names:
                    print_green(f"Describing {kind} '{resource_name}':\n")
                    command_describe = f"kubectl -n {ns} describe {kind} {resource_name}"
                    result = run_command(command_describe)

                    if result:
                        print(result.decode('utf-8'))
                    else:
                        print_red(f"Failed to describe {kind} '{resource_name}'.\n")
            else:
                print_red(f"No {kind}(s) found in namespace '{ns}'.\n")
        else:
            print_red(f"No match found for '{user_kind_input}'. Please try again.")


# This deletes all the resources from the given namespace
def deleteResourcesForce(namespace, args):
    kinds = ["virtualnic", "networkinterface", "networkendpoint", "lbpoolmember", "lblistener", "lbpool", "loadbalancer", "virtualnetworkinterface","sharemounttarget", "reservedip", "ipaddress", "network", "securitygroup", "networkacl", "routingtable", "clusternetwork", "publicaddressrange", "router"]
    ns = namespace
    print_red(f"Deleting resources from the namespace {ns}: \n")

    for kind in kinds:
        numbers = run_command(f"kubectl -n {ns} get {kind} --no-headers -o custom-columns=:metadata.name | wc -l")

        print_red(f"\nDeleting {numbers.decode('utf-8')} {kind}s")


        # Get the list of objects to delete in order
        result = subprocess.run([f"kubectl -n {ns} get {kind} --no-headers -o custom-columns=:metadata.name"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            objects = result.stdout.splitlines()

            # Delete each object of that kind
            for obj in objects:
                obj = obj.decode('utf-8')
                print(obj)
                subprocess.run([f"kubectl -n {ns} delete {kind} {obj} --wait=false"], shell=True)
        else:
            print_red(f"Failed to get {kind}s. Error: {result.stderr}")

    # Deletes the saved txt and yaml files to avoid obsolete data
    if not args.yes:
        if os.path.exists("./applied_resources.txt"):
            choice = input("Do you want to delete the 'applied_resources.txt/.yaml' files? (y/n): ")
            if choice.lower() in ['yes', 'y']:
                if os.path.exists("./applied_resources.txt"):
                    run_command("rm ./applied_resources.txt")
                if os.path.exists("./applied_resources.yaml"):
                    run_command("rm ./applied_resources.yaml")
            else:
                print("applied_resources files are retained")

    # Deletes the saved txt and yaml files of CVSI STRESS TEST to avoid obsolete data
    if not args.yes:
        if os.path.exists("./cvsi_VirtualNics/"):
            choice = input("Do you want to delete the CVSI VNIC files? (y/n): ")
            if choice.lower() in ['yes', 'y']:
                if os.path.exists("./cvsi_VirtualNics/"):
                    run_command("rm -rf ./cvsi_VirtualNics/")
            else:
                print("CVSI VNIC files are retained")


def delete_resources(namespace, args): # This is the safest way to delete all the resources, It will wait and confirm all the resources are deleted from a kind before moving to the next kind
    kinds_in_dependency_order = reversed(K8S_RESOURCE_KINDS)
    ns = namespace
    all_kinds_to_delete = []

    print_yellow(f"Checking resources to be deleted from the '{ns}' namespace...")

    # First, find all resources that exist
    for kind in kinds_in_dependency_order:
        command = f"kubectl get {kind} -n {ns} --no-headers --ignore-not-found=true -o custom-columns=:metadata.name 2>/dev/null"
        try:
            resources = subprocess.check_output(command, shell=True, universal_newlines=True).strip().split('\n')
            if resources and resources[0]:
                all_kinds_to_delete.append((kind, resources))
        except subprocess.CalledProcessError:
            continue

    if not all_kinds_to_delete:
        print_green("No resources found to delete.")
        return

    # Present a summary and get confirmation
    print_red("\nThe following resources will be permanently deleted:")
    print_red("+---------------------------+---------+")
    print_red(f"| {'Resource Kind':<25} | {'Count':<7} |")
    print_red("+---------------------------+---------+")
    for kind, resources in all_kinds_to_delete:
        print_red(f"| {kind:<25} | {len(resources):<7} |")
    print_red("+---------------------------+---------+")

    if not args.yes:
        try:
            confirm = input("\nAre you sure you want to proceed? (y/n): ").lower()
            if confirm not in ['y', 'yes']:
                print_yellow("Deletion cancelled by user.")
                return
        except KeyboardInterrupt:
            print_yellow("\n\nDeletion cancelled by user.")
            return

    # Proceed with deletion and continuous feedback
    print_green("\nStarting deletion...")
    for kind, resources in all_kinds_to_delete:
        initial_count = len(resources)
        print_green(f"-> Deleting {initial_count} {kind}(s)...")

        for resource_name in resources:
            print(f"- Issuing delete for {kind} '{resource_name}'")
            delete_command = f"kubectl delete {kind} {resource_name} -n {ns} --wait=false" # making it false so we can see the progress, but it wont move to next resource until its deleted
            subprocess.run(delete_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        start_time = time.time()
        timeout = 180  # Max 3 minutes timeout per resource kind
        if kind in ["virtualnic", "networkinterface", "networkendpoint"]:
            timeout = 600  # Max 10 minutes for VNIC, NIF, NEP
        while True:
            get_command = f"kubectl get {kind} -n {ns} --no-headers --ignore-not-found=true -o custom-columns=:metadata.name 2>/dev/null"
            try:
                remaining_resources = subprocess.check_output(get_command, shell=True, universal_newlines=True).strip().split('\n')
                if not remaining_resources or not remaining_resources[0]:
                    remaining_count = 0
                else:
                    remaining_count = len(remaining_resources)
            except subprocess.CalledProcessError:
                remaining_count = 0

            status_line = f"   Waiting for {remaining_count} of {initial_count} {kind}(s) to be deleted...(wait time: {timeout/60} minutes max)"
            print_red(status_line, end='\r', flush=True)

            if remaining_count == 0:
                print(" " * len(status_line), end='\r') 
                print_green(f"   All {kind}(s) have been deleted.")
                break

            if time.time() - start_time > timeout:
                print("\n")
                print_yellow(f"   Warning: Timeout reached while waiting for {kind}(s) to be deleted.")
                print_yellow(f"   The following resources might be stuck: {remaining_resources}")
                break

            time.sleep(1)
            
    print_green("\nDeletion process completed.")

    # Deletes the saved txt and yaml files to avoid obsolete data
    if not args.yes:
        if os.path.exists("./applied_resources.txt"):
            choice = input("Do you want to delete the 'applied_resources.txt/.yaml' files? (y/n): ")
            if choice.lower() in ['yes', 'y']:
                if os.path.exists("./applied_resources.txt"):
                    run_command("rm ./applied_resources.txt")
                if os.path.exists("./applied_resources.yaml"):
                    run_command("rm ./applied_resources.yaml")
            else:
                print("applied_resources files are retained")

    # Deletes the saved txt and yaml files of CVSI STRESS TEST to avoid obsolete data
    if not args.yes:
        if os.path.exists("./cvsi_VirtualNics/"):
            choice = input("Do you want to delete the CVSI VNIC files? (y/n): ")
            if choice.lower() in ['yes', 'y']:
                if os.path.exists("./cvsi_VirtualNics/"):
                    run_command("rm -rf ./cvsi_VirtualNics/")
            else:
                print("CVSI VNIC files are retained")
            
            
# ----------------------------------------------------------------------------------------

def deleteResourcesInteractive(namespace):
    ns = namespace
    kinds_in_dependency_order = [
        "lbpoolmember", "lblistener", "lbpool", "loadbalancer",
        "virtualnic", "networkinterface", "networkendpoint",
        "sharemounttarget", "virtualnetworkinterface", "reservedip", "ipaddress",
        "network", "securitygroup", "networkacl", "routingtable", "publicaddressrange",
        "clusternetwork", "router"
    ]

    while True:
        print_green("\nInteractive Deletion Mode")
        print_yellow(f"Namespace: {ns}")

        # Discover available resources
        available_kinds = {}
        for kind in kinds_in_dependency_order:
            command = f"kubectl get {kind} -n {ns} --no-headers --ignore-not-found=true -o custom-columns=:metadata.name 2>/dev/null"
            try:
                resources = subprocess.check_output(command, shell=True, universal_newlines=True).strip().split('\n')
                if resources and resources[0]:
                    available_kinds[kind] = resources
            except subprocess.CalledProcessError:
                continue

        if not available_kinds:
            print_green("No resources found to delete in this namespace.")
            break

        # Display resource kinds menu
        print_green("\nSelect a resource kind to delete:")
        kind_menu = list(available_kinds.keys())
        for i, kind in enumerate(kind_menu):
            print(f"  {i + 1}: {kind} ({len(available_kinds[kind])})")
        print("  0: Exit")

        try:
            choice = input("Enter your choice: ")
            if not choice.isdigit() or not (0 <= int(choice) <= len(kind_menu)):
                print_red("Invalid choice. Please try again.")
                continue
            choice = int(choice)
            if choice == 0:
                break

            selected_kind = kind_menu[choice - 1]
            resources_to_delete = available_kinds[selected_kind]

            # Display resources of the selected kind
            print_green(f"\nSelect resources of kind '{selected_kind}' to delete:")
            for i, resource in enumerate(resources_to_delete):
                print(f"  {i + 1}: {resource}")
            print("  all: Delete all resources of this kind")
            print("  back: Go back to the previous menu")

            resource_choice = input("Enter numbers (e.g., 1,3,5), 'all', or 'back': ").lower()

            if resource_choice == 'back':
                continue

            to_be_deleted = []
            if resource_choice == 'all':
                to_be_deleted = resources_to_delete
            else:
                try:
                    indices = [int(i.strip()) - 1 for i in resource_choice.split(',')]
                    for i in indices:
                        if 0 <= i < len(resources_to_delete):
                            to_be_deleted.append(resources_to_delete[i])
                        else:
                            print_red(f"Invalid index: {i+1}")
                except ValueError:
                    print_red("Invalid input. Please enter numbers separated by commas, 'all', or 'back'.")
                    continue

            if not to_be_deleted:
                print_yellow("No resources selected for deletion.")
                continue

            # Confirmation
            print_red("\nThe following resources will be permanently deleted:")
            for resource in to_be_deleted:
                print(f"  - {selected_kind}: {resource}")
            
            confirm = input("Are you sure you want to proceed? (y/n): ").lower()
            if confirm in ['y', 'yes']:
                for resource in to_be_deleted:
                    delete_command = f"kubectl delete {selected_kind} {resource} -n {ns} --wait=false"
                    print_green(f"Executing: {delete_command}")
                    run_command(delete_command)
                print_green("Deletion commands executed.")
            else:
                print_yellow("Deletion cancelled.")

        except (KeyboardInterrupt, EOFError):
            print_yellow("\n\nOperation cancelled by user.")
            break

# This uses applied_resources.txt file to delete resources. You can modify it as per your requirement
def deleteCurrentResources(file_path, args):

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            lines = file.readlines()
            confirmation = True
            res_count = 0
            for line in reversed(lines):
                parts = line.strip().split(", ")

                if len(parts) == 3:
                    namespace, kind, name = parts
                    if kind and namespace and name:
                        if not args.yes:
                            if confirmation:
                                response = input(f"Do you want to proceed with deleting the resource in namespace \"{namespace}\"? (y/n): ")
                                if response.lower() in ["y", "yes"]:
                                    confirmation = False
                                else:
                                    print("Stopping Deletion")
                                    sys.exit(1)

                        delete_command = f'kubectl delete {kind.lower()} -n {namespace} {name} --wait=false'
                        print(f"Deleting {kind} in namespace - {namespace} with name - {name}")
                        result = run_command(delete_command)
                        if result:
                            print(result)
                            res_count += 1
                    else:
                        print(f"Invalid line in file: {line}")
                else:
                    print(f"{line}")
            print(f"Total resources deleted: {res_count}")
            print("Deleting the Applied_Resources.txt file... ")
            run_command(f"rm {file_path}")
    else:
        print("The applied_resources.txt file does NOT exist.")


def get_vnic_status(ns, args=None):
    def get_virtual_nics(ns):
        try:
            # Run the kubectl command to get the virtual NICs
            command = ["kubectl", "get", "virtualnics", "-n", ns, "-o", "custom-columns=NAME:.metadata.name", "--no-headers"]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            if result.returncode != 0:
                print(f"Error occurred: {result.stderr}")
                return []

            if not result.stdout.strip():
                return []

            virtual_nics = result.stdout.strip().split('\n')
            return virtual_nics

        except subprocess.CalledProcessError as e:
            print(f"Error occurred while executing the command: {e.stderr}")
            return []

    def get_network_interfaces(ns):
        try:
            command = ["kubectl", "get", "networkinterface", "-n", ns, "-o", "custom-columns=NAME:.metadata.name", "--no-headers"]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if result.returncode != 0:
                return []
            if not result.stdout.strip():
                return []
            network_interfaces = result.stdout.strip().split('\n')
            return network_interfaces

        except subprocess.CalledProcessError as e:
            print(f"Error occurred while executing the command: {e.stderr}")
            return []

    def get_interface_name(vnic, ns):
        try:
            command = f"kubectl get virtualnic {vnic} -n {ns} -o json"
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)

            if result.returncode != 0:
                print(f"Error getting virtualnic {vnic}: {result.stderr}")
                return None

            vnic_json = json.loads(result.stdout)
            
            interface_name = vnic_json.get('status', {}).get('networkInterface', {}).get('Name', None)

            if not interface_name:
                print(f"Could not find networkInterface Name for {vnic} in status.")
                return None

            return interface_name

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for virtualnic {vnic}: {e}")
            return None
        except Exception as e:
            print(f"An exception occurred while getting interface name for {vnic}: {e}")
            return None

    def check_interface_ready(interface_name, ns):
        try:
            command = f"kubectl get networkinterface {interface_name} -n {ns} -o json"
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)

            if result.returncode != 0:
                print(f"Error getting networkinterface {interface_name}: {result.stderr}")
                return False, None

            nif_json = json.loads(result.stdout)
            
            is_ready = nif_json.get('status', {}).get('ready', False)
            local_port_id = nif_json.get('status', {}).get('portID', None)

            return is_ready, local_port_id

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for networkinterface {interface_name}: {e}")
            return False, None
        except Exception as e:
            print(f"An exception occurred while checking ready status for {interface_name}: {e}")
            return False, None

    print_green(f"Fetching Virtual NICs in {ns} namespace..")
    virtual_nics = get_virtual_nics(ns)
    
    processed_nifs = []
    if len(virtual_nics) > 0 and virtual_nics != ['']:
        print_green(f"Total number of Virtual NICs found : {len(virtual_nics)}")
        print(f"VNICS names in {ns} namespace :{virtual_nics}\n ")

        for vnic in virtual_nics:
            print_green(f"Processing VNIC: {vnic}")

            interface_name = get_interface_name(vnic, ns)
            if not interface_name:
                print(f"Failed to get interface name for {vnic}")
                continue

            processed_nifs.append(interface_name)

            is_ready, local_port_id = check_interface_ready(interface_name, ns)
            if is_ready:
                print(f"The network interface {interface_name} is ready.")
                print("NIF Status Check : \033[92mOK\033[0m\n")
            else:
                print(f"The network interface {interface_name} is not ready.")
                print("NIF Status Check : \033[91mERROR\033[0m\n")

            if local_port_id:
                print(f"Local Port ID: {local_port_id}\n")
            else:
                print("Failed to get Local Port ID\n")
    
    print_green("Checking for Network Interfaces (NEP/NIF mode)..")
    network_interfaces = get_network_interfaces(ns)
    
    if len(network_interfaces) > 0 and network_interfaces != ['']:
        network_interfaces = [nif for nif in network_interfaces if nif not in processed_nifs]
        if len(network_interfaces) > 0:
            print_green(f"Total number of Network Interfaces found (Standalone) : {len(network_interfaces)}")
            for nif in network_interfaces:
                print_green(f"Processing NIF: {nif}")
                is_ready, local_port_id = check_interface_ready(nif, ns)
                if is_ready:
                    print(f"The network interface {nif} is ready.")
                    print("NIF Status Check : \033[92mOK\033[0m\n")
                else:
                    print(f"The network interface {nif} is not ready.")
                    print("NIF Status Check : \033[91mERROR\033[0m\n")

                if local_port_id:
                    print(f"Local Port ID: {local_port_id}\n")
                else:
                    print("Failed to get Local Port ID\n")
    else:
        if not processed_nifs:
            print_green("No Network Interfaces found either.")

def cvsi_stresstest(ns, args):
    if args.vnitype != 'cvsi':
        print_red("The cvsistress action requires the -vni flag to be set to 'cvsi'.")
        sys.exit(1)
    print_green("Running CVSI Stress Tests")
    vnics_names_file = './cvsi_VirtualNics/vnics_names_file.txt'  # File containing the list of VNIC YAML file names
    vnics_dir = './cvsi_VirtualNics'  # Directory where the VNIC YAML files are located
    iterations = int(input("Enter the number of iterations: ") or 1)  # Number of iterations of create/Delete
    sleep_time = 1  # Time to wait between commands (in seconds)

    # Check if the vnics_names_file exists
    if not os.path.isfile(vnics_names_file):
        print_red(f"\nError: Prerequisite files not found in '{vnics_dir}'.")
        print_yellow("The 'cst' action requires CVSI resource YAMLs to be generated first.")
        print_green("\nPlease run the following command to create them, and then try 'cst' again:")
        print(f"  ./netsim.py create --vnitype cvsi --namespace {ns}")
        sys.exit(1)

    def delete_vnics():

        with open(vnics_names_file, 'r') as file:
            vnic_names = file.read().splitlines()

        for vnic_name in vnic_names:
            yaml_path = f"{vnics_dir}/{vnic_name}.yaml"
            if not os.path.isfile(yaml_path):
                print_red(f"FILE Error: YAML file '{yaml_path}' does not exist. Skipping...")
                continue
            print_red(f"Deleting VNIC: {vnic_name}")
            op = run_command(f"kubectl delete -f {yaml_path}")
            print(op.decode('utf-8'))

    def recreate_vnics():

        with open(vnics_names_file, 'r') as file:
            vnic_names = file.read().splitlines()

        for vnic_name in vnic_names:
            yaml_path = f"{vnics_dir}/{vnic_name}.yaml"
            if not os.path.isfile(yaml_path):
                print_red(f"FILE Error: YAML file '{yaml_path}' does not exist. Skipping...")
                continue
            print_green(f"Recreating VNIC: {vnic_name}")
            op = run_command(f"kubectl apply -f {yaml_path}")
            print(op.decode('utf-8'))

    def check_vnic_count(nodes):

        for node in nodes:
            command = f"./scripts/netinfo list net-core | grep Local | grep {node.decode('utf-8')} | wc -l"
            print(f"Running the command: {command}")
            result = run_command(command)
            if result:
                vnic_count = result.decode('utf-8').strip()
                print(f"VNIC count: {vnic_count} (Per Node)")
                return int(vnic_count)
            else:
                print(f"Error executing command: {result.stderr}")
                return None


    def check_for_leaked(action, nodes):
        if action == "delete":
            vnic_count_after_delete = check_vnic_count(nodes)
            if vnic_count_after_delete == 0:
                print("VNICs deleted successfully, count is 0.")
                print_green("NO LEAKED OBJECTS FOUND\n")
            else:
                print_red(f"Warning: VNIC count after delete is {vnic_count_after_delete}, expected 0. Few Objects may have leaked.")

        elif action == "recreate":
            vnic_count_after_recreate = check_vnic_count(nodes)
            expected_count = len(open(vnics_names_file).readlines())
            expected_count = expected_count // len(nodes)
            if vnic_count_after_recreate == expected_count:
                print(f"VNICs recreated successfully, count is {vnic_count_after_recreate} (Per Node).")
                print_green("NO LEAKED OBJECTS FOUND\n")
            else:
                print_red(f"Warning: VNIC count after recreate is {vnic_count_after_recreate}, expected {expected_count}.")

        else:
            print_red("Invalid action. Please check the calling function.")
            sys.exit(1)

    def stress_test_vnics():
        setup_and_load_globals(args.namespace, args)
        nodes = get_compute_nodes(specificnode, excludenode)
        for iteration in range(1, iterations + 1):
            print(f"------------Iteration {iteration}------------")
            print_red(f"Deleting {len(open(vnics_names_file).readlines())} VNICs from each node...")
            delete_vnics()
            # time.sleep(sleep_time)
            check_for_leaked("delete", nodes)

            print_green(f"Recreating {len(open(vnics_names_file).readlines())} VNICs for each node...")
            recreate_vnics()
            # time.sleep(sleep_time)
            check_for_leaked("recreate", nodes)
            print(f"------------Iteration {iteration} completed------------")

        deleteall = input("Do you want to delete all other resources? (y/n): ").lower()
        if deleteall == "y":
            print("Deleting the VNICS resoruces completely")
            delete_vnics()  # Deletes all the VNICS from the namespace
            print_green("All VNICS deleted successfully")
            print_red("Deleting all the other resources...")
            time.sleep(5)
            delete_resources(ns) # Deletes all the other resources
            
    stress_test_vnics()

#End of the script

def force_delete_objects(namespace, target=None):
    """
    Finds and force-deletes Kubernetes objects stuck in a 'Terminating' state
    by removing their finalizers.
    """
    print_green(f"Starting force-delete scan in namespace '{namespace}'...")
    
    stuck_objects = []
    kinds_to_scan = []
    
    # Heuristic to decide if the target is a kind or a name
    is_kind = False
    if target:
        # Match against known K8S resource kinds
        if difflib.get_close_matches(target, K8S_RESOURCE_KINDS, n=1, cutoff=0.8):
             is_kind = True

    # --- Find objects to scan ---
    
    # Mode 3: Target is a specific resource name
    if target and not is_kind:
        print_yellow(f"Mode: Targeting specific resource name '{target}'...")
        found_resource = False
        for kind in K8S_RESOURCE_KINDS:
            command = f"kubectl get {kind} {target} -n {namespace} -o json"
            # Suppress stderr for this command as we expect many "not found" errors
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    resource = json.loads(result.stdout)
                    stuck_objects.append(resource)
                    print_green(f"  -> Found target as {kind}/{target}.")
                    found_resource = True
                    break 
                except json.JSONDecodeError:
                    print_red(f"Error parsing JSON for {kind}/{target}.")
        if not found_resource:
             print_red(f"Error: Could not find any resource with the name '{target}' in namespace '{namespace}'.")
             return

    # Mode 1 & 2: Target is a kind or all kinds
    else:
        if target and is_kind:
            matched_kind = difflib.get_close_matches(target, K8S_RESOURCE_KINDS, n=1, cutoff=0.8)[0]
            print_yellow(f"Mode: Targeting resource kind '{matched_kind}'...")
            kinds_to_scan = [matched_kind]
        else:
            print_yellow("Mode: Targeting all known resource kinds...")
            kinds_to_scan = K8S_RESOURCE_KINDS

        for kind in kinds_to_scan:
            print(f"  - Scanning {kind}s...")
            command = f"kubectl get {kind} -n {namespace} -o json"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                continue

            try:
                resource_list = json.loads(result.stdout)
                for item in resource_list.get("items", []):
                    stuck_objects.append(item)
            except json.JSONDecodeError:
                print_red(f"Could not parse JSON output for kind {kind}.")

    # --- Filter for stuck objects ---
    final_stuck_list = []
    for obj in stuck_objects:
        metadata = obj.get("metadata", {})
        if metadata.get("deletionTimestamp") and metadata.get("finalizers"):
            final_stuck_list.append({
                "kind": obj.get("kind"),
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace")
            })

    if not final_stuck_list:
        print_green("\nNO stuck objects with finalizers found.")
        return

    # --- Confirmation Step ---
    print_red("\n" + "="*60)
    print_red("!! WARNING: DESTRUCTIVE ACTION !!")
    print_red("="*60)
    print_yellow("The following objects are stuck in a 'Terminating' state:")
    for obj in final_stuck_list:
        print(f"  - {obj['kind']}: {obj['name']}")
    
    print_red("\nThis action will forcefully remove their finalizers to allow deletion.")
    print_red("This can be dangerous and is not reversible. Also may cause leaked objects on the net-core.")
    
    try:
        confirm = input("Are you absolutely sure you want to proceed? (yes/no): ").lower()
    except (KeyboardInterrupt, EOFError):
        print_yellow("\nOperation cancelled.")
        return

    if confirm not in ['yes', 'y']:
        print_yellow("Operation cancelled by user.")
        return

    # --- Patching Step ---
    print_green("\nProceeding with finalizer removal...")
    for obj in final_stuck_list:
        kind = obj['kind']
        name = obj['name']
        ns = obj['namespace']
        patch_command = f"kubectl patch {kind} {name} -n {ns} --type='merge' -p '{{\"metadata\":{{\"finalizers\":[]}}}}'"
        
        print(f"  - Patching {kind}/{name}...")
        result = subprocess.run(patch_command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print_green(f"    Success: {result.stdout.strip()}")
        else:
            print_red(f"    Error patching {kind}/{name}: {result.stderr.strip()}")

    print_green("\nForce-deletion process complete.")


def detect_leaks():
    
    GET_LEAKS_SCRIPT_PATH = "./scripts/get_leaks.sh"
    
    if not os.path.exists(GET_LEAKS_SCRIPT_PATH):
        print_red(f"Error: Leak detection script not found at '{GET_LEAKS_SCRIPT_PATH}'.")
        print_yellow("Please ensure the script is in the correct location.")
        return

    if not os.access(GET_LEAKS_SCRIPT_PATH, os.X_OK):
        print_red(f"Error: Leak detection script at '{GET_LEAKS_SCRIPT_PATH}' is not executable.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        print_green(f"Using temporary directory for logs: {temp_dir}")
        logs_path = os.path.join(temp_dir, "logs")
        print_yellow("Preparing to run leak detection script... This relies on ~./scripts/get_leaks.sh~")

        try:
            # --- First Pass ---
            print_green("\n--- Running leak detection (Pass 1 of 2) ---")
            print_yellow("This may take sometime...")
            run_args = [GET_LEAKS_SCRIPT_PATH, "-l", logs_path]
            
            process1 = subprocess.run(
                run_args,
                capture_output=True, text=True
            )

            print_green("--- Script Output (Pass 1) ---")
            if process1.stdout:
                print(process1.stdout)
            if process1.stderr:
                print_red(process1.stderr)
            print_green("------------------------------")

            if process1.returncode != 0:
                print_red("Error during the first pass of the leak detection script. See output above.")
                return

            # --- Second Pass ---
            print_green("\n--- Running leak detection (Pass 2 of 2) ---")
            process2 = subprocess.run(
                run_args,
                capture_output=True, text=True
            )
            
            print_green("--- Script Output (Pass 2) ---")
            if process2.stdout:
                print(process2.stdout)
            if process2.stderr:
                print_red(process2.stderr)
            print_green("------------------------------")

            if process2.returncode != 0:
                print_red("Error during the second pass of the leak detection script. See output above.")
                return
            
            # --- Process Results ---
            print_green("\n--- Processing results ---")
            comm_file_path = os.path.join(logs_path, "leaked_objects.log.comm")

            if not os.path.exists(comm_file_path):
                print_yellow("Could not find the 'leaked_objects.log.comm' file.")
                print_green(" No leaked objects found.")
                return

            with open(comm_file_path, 'r') as f:
                leaks = f.readlines()

            leaks = [line.strip() for line in leaks if line.strip()]

            if not leaks:
                print_green(" No leaked objects found.")
                return
            
            # Parse and group leaks by node
            leaks_by_node = {}
            for leak in leaks:
                try:
                    parts = leak.split(';')
                    if len(parts) < 2: continue

                    node_part = parts[0]
                    obj_part = parts[1]
                    
                    if '=' not in node_part or '=' not in obj_part: continue

                    node_name = node_part.split('=', 1)[1]
                    obj_type = obj_part.split('=', 1)[0].strip()
                    obj_id = obj_part.split('=', 1)[1]

                    if node_name not in leaks_by_node:
                        leaks_by_node[node_name] = []
                    
                    leaks_by_node[node_name].append(f"- {obj_type.ljust(10)}: {obj_id}")
                except IndexError:
                    print_yellow(f"Could not parse line: {leak}")


            # Display formatted output
            print_red("\nLeaked Objects Summary")
            print_red("------------------------------------")
            print_red(f"Total Leaks Found: {len(leaks)}")
            print_red("------------------------------------")

            for node, objects in sorted(leaks_by_node.items()):
                leak_count = len(objects)
                plural_s = 's' if leak_count > 1 else ''
                print_yellow(f"\nLeaks on node '{node}' ({leak_count} leak{plural_s} found):")
                for obj_str in objects:
                    print(f"   {obj_str}")

            print_red("\n------------------------------------")
            print_yellow("Tip: Use 'scripts/nettools/rm_leaked_objects.sh' to clean up these objects.")

        except FileNotFoundError:
            print_red(f"Error: The script '{GET_LEAKS_SCRIPT_PATH}' was not found.")
            return
        except Exception as e:
            print_red(f"An unexpected error occurred: {e}")

    print_green("\nLeak detection process finished.")