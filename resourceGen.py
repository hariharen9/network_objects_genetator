#!/usr/bin/env python3

import subprocess
import os
import time
import uuid
import sys
from datetime import datetime
import json
import yaml
import random
import argparse
import string
import ipaddress
import re


#Helper functions
def print_red(text):
    print("\033[91m" + str(text) + "\033[0m")
def print_green(text):
    print("\033[92m" + str(text) + "\033[0m")

def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.stdout

def run_command_strip(command):
    outp = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    if outp.returncode != 0:
        print(f"Error: {outp.stderr}")
    return outp.stdout.strip()

def apply(command, kind):
    print(f"Applying {kind}..")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    print(result.stdout)
    return result.stdout

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

def generate_route_distinguisher():
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

def time_taken(start_time):
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
    global serviceGatewayIP_address
    global serviceGatewayIP_range
    serviceGatewayIP_address = f"192.21.{routerIndex}.{routerIndex}"
    serviceGatewayIP_range = f"192.21.{routerIndex}.0/24"

    return serviceGatewayIP_address

def generate_serviceGatewayStaticRoutes(routerIndex):
    serviceGatewayStaticRoutes_ips = [
        f"192.21.{routerIndex + 1}.0/24",
        f"192.21.{routerIndex + 2}.0/24"
    ]
    return serviceGatewayStaticRoutes_ips

def generate_addressPrefixes(routerIndex):
    global address_prefix_1
    global address_prefix_2

    address_prefix_1 = f"192.62.{routerIndex}.0/24"
    address_prefix_2 = f"192.62.{routerIndex + 1}.0/24"

    address_prefixes = [
        f"{address_prefix_1}",
        f"{address_prefix_2}"
    ]
    return address_prefixes


def create_shell_scripts(vpcid, allres, loadbalancer, doapply):
    if not doapply:
        os.chdir(f"./{vpcid}")

        print("The resources are \033[91mNOT\033[0m applied, creating the shell scripts to apply/delete")
        # Script to apply all base k8s objects
        with open("apply_basek8s.sh", "w") as f:
            for filename in os.listdir("."):
                if filename.startswith("Router") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir("."):
                if filename.startswith("RoutingTable") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir("."):
                if filename.startswith("SecurityGroup") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir("."):
                if filename.startswith("NetworkACL") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")
            for filename in os.listdir("."):
                if filename.startswith("Network") and filename.endswith(".yaml") and "NetworkACL" not in filename:
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")


        os.chmod("apply_basek8s.sh", 0o755)


# CLEANUP SCRIPT
        cleanup_script_content = f"""\
kinds=(virtualnic networkinterface networkendpoint lbpoolmember lblistener lbpool loadbalancer virtualnetworkinterface sharemounttarget reservedip ipaddress network securitygroup networkacl routingtable router)
for kind in ${{kinds[@]}}; do
  echo "deleting "$kind"s"
  for obj in $(kubectl -n {ns} get $kind | grep -v NAME | awk '{{ print $1 }}') ; do
    echo $obj
    kubectl -n {ns} delete $kind $obj
  done
done
"""
        with open("cleanup.sh", "w") as file:
            file.write(cleanup_script_content)

        os.chmod("cleanup.sh", 0o755)


        # Script to apply all the VNIC files
        with open("apply_vnic.sh", "w") as f:
            for filename in os.listdir("."):
                if filename.startswith("VirtualNic") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl apply -f {filename}\n")

        os.chmod("apply_vnic.sh", 0o755)

                # Script to delete all the VNICs
        with open("delete_vnic.sh", "w") as f:
            for filename in os.listdir("."):
                if filename.startswith("VirtualNic") and filename.endswith(".yaml"):
                    f.write(f"echo {filename}\n")
                    f.write(f"kubectl delete -f {filename}\n")

        os.chmod("delete_vnic.sh", 0o755)


        # Script to apply all the VNI and RIPs
        if allres:
            with open("apply_vni.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("VirtualNetworkInterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")

            os.chmod("apply_vni.sh", 0o755)


            with open("apply_rip.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("ReservedIP") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")

            os.chmod("apply_rip.sh", 0o755)


            with open("apply_smt.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("ShareMountTarget") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")

            os.chmod("apply_smt.sh", 0o755)


            with open("apply_vniresources.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("ReservedIP") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("ShareMountTarget") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                    if filename.startswith("VirtualNetworkInterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")

            os.chmod("apply_vniresources.sh", 0o755)



            with open("delete_vniresources.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("VirtualNetworkInterface") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("ShareMountTarget") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                    if filename.startswith("ReservedIP") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")

            os.chmod("delete_vniresources.sh", 0o755)


        # Script to Apply all the lb
        if loadbalancer == 'yes':
            with open("apply_lb.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("LBPoolMember") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir("."):
                    if filename.startswith("LBListener") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir("."):
                    if filename.startswith("LBPool") and filename.endswith(".yaml") and "member" not in filename:
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")
                for filename in os.listdir("."):
                    if filename.startswith("LoadBalancer") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl apply -f {filename}\n")

            os.chmod("apply_lb.sh", 0o755)


            # Script to delete all the lb
            with open("delete_lb.sh", "w") as f:
                for filename in os.listdir("."):
                    if filename.startswith("LBPoolMember") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir("."):
                    if filename.startswith("LBListener") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir("."):
                    if filename.startswith("LBPool") and filename.endswith(".yaml") and "member" not in filename:
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")
                for filename in os.listdir("."):
                    if filename.startswith("LoadBalancer") and filename.endswith(".yaml"):
                        f.write(f"echo {filename}\n")
                        f.write(f"kubectl delete -f {filename}\n")

            os.chmod("delete_lb.sh", 0o755)

        # Print Test Files created
        yaml_files = sorted([file for file in os.listdir() if file.endswith('.yaml')])
        yaml_count = len(yaml_files)
        print("Test Files created: \n", " ".join(yaml_files), f"\n(Total: {yaml_count})")

        # Print scripts created
        sh_files = sorted([file for file in os.listdir() if file.endswith('.sh')])
        sh_count = len(sh_files)
        print("Scripts created: \n", " ".join(sh_files), f"\n(Total: {sh_count})")
        os.chdir("..")



#----------------------------------------------------------------------------------------
#   ROUTER
#----------------------------------------------------------------------------------------
def create_router():

    print_green(f"\nCreating Resources for VPCID: {vpcid}")
    print_green(f"\nCreating Router")

    reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    router_template = template_data["routerTemplate"].copy()
    router_template["metadata"]["annotations"]["RequestID"] = reqid
    router_template["metadata"]["namespace"] = ns
    router_template["metadata"]["name"] = rName
    router_template["metadata"]["labels"]["VPCID"] = vpcid
    router_template["spec"]["vpcid"] = vpcid
    router_template["spec"]["routeDistinguisher"] = generate_route_distinguisher()
    router_template["spec"]["addressPrefixes"] = generate_addressPrefixes(routerIndex)
    #print("addressPrefixes =", router_template["spec"]["addressPrefixes"])
    router_template["spec"]["serviceGatewayIP"] = generate_serviceGatewayIP(routerIndex)
    #print("serviceGatewayIP =" , router_template["spec"]["serviceGatewayIP"])
    router_template["spec"]["serviceGatewayStaticRoutes"] = generate_serviceGatewayStaticRoutes(routerIndex)
    #print("serviceGatewayStaticRoutes =" , router_template["spec"]["serviceGatewayStaticRoutes"])

    applying(router_template)


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

    for route in rtr_table_template["spec"]["routes"]:
        route["uuid"] = f"{rPrefix}-{str(uuid.uuid4())}"

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

    for route in ingress_rt_template["spec"]["routes"]:
        route["uuid"] = f"{rPrefix}-{str(uuid.uuid4())}"

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
        sg_template["spec"]["vpcid"] = vpcid
        sg_template["spec"]["rules"][0]["uid"] = f"{rPrefix}-{str(uuid.uuid4())}"

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
        nacl_template["spec"]["vpcid"] = vpcid
        nacl_template["spec"]["rules"][0]["uid"] = f"{rPrefix}-{str(uuid.uuid4())}"
        nacl_template["spec"]["rules"][1]["uid"] = f"{rPrefix}-{str(uuid.uuid4())}"

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
        subnet = f"192.168.{netnum}.0/24"
        nws.append(nw)

        nw_template = template_data["networkTemplate"].copy()

        nw_template["metadata"]["annotations"]["RequestID"] = reqid
        nw_template["metadata"]["labels"]["VPCID"] = vpcid
        nw_template["metadata"]["namespace"] = ns
        nw_template["metadata"]["name"] = nw
        nw_template["metadata"]["uid"] = f"{str(uuid.uuid4())}"
        nw_template["spec"]["routerName"] = rName
        nw_template["spec"]["cidr"] = subnet
        nw_template["spec"]["aclName"] = naclName
        nw_template["spec"]["publicGatewayUID"] = f"{rPrefix}-{str(uuid.uuid4())}"
        nw_template["spec"]["publicGatewayIP"] = generate_ip_address(serviceGatewayIP_range)
        nw_template["spec"]["routingTableName"] = rtrTableName

        applying(nw_template)

#----------------------------------------------------------------------------------------
#   FOREIGN NETWORK FILES
#----------------------------------------------------------------------------------------

def create_foreign_networks():
    print_green("\nCreating Foreign Networks")

    for netnum in range(1, nwcount + 1):
        reqid = f"{netnum}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
        fnw = f"{mz}-{str(uuid.uuid4())}"
        subnet = f"192.22.1{netnum}.0/28"
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
        fnw_template["spec"]["publicGatewayIP"] = f"192.82.22.{netnum}"
        fnw_template["spec"]["routingTableName"] = rtrTableName

        applying(fnw_template)



#----------------------------------------------------------------------------------------
#   VIRTUAL NETWORK / VNICs
#----------------------------------------------------------------------------------------

def create_vnics():
    print_green("\nCreating VirtualNics (VNIC)")
    nodes = run_command("kubectl -n genctl get nodes --show-labels | grep compute | awk '{print $1}'").split()

    # Filter nodes based on specificnode and excludenode
    if specificnode:
        nodes = [node for node in nodes if node.decode('utf-8') in specificnode]
    if excludenode:
        nodes = [node for node in nodes if node.decode('utf-8') not in excludenode]

    print(f"Number of Nodes:{len(nodes)}")
    print(f"Nodes: {nodes}")

    global vnic_names
    fipcount = 0
    netnum = 0
    vnic_names = []

    # Verifying for DualNICs
    def verifydnic(node):
        global dnic
        commandToVerifyDNIC = f"kubectl describe node {node.decode('utf-8')} -n genctl | grep genctl.smartnic=true"
        ddnic = run_command_strip(commandToVerifyDNIC)
        if ddnic == "genctl.smartnic=true":
            print(f"This node - {node} is a Dual NIC Node, Fetching the tunnelEndpointIP")
            dnic = True
        else:
            dnic = False



    for nw in nws:
        netnum += 1
        for i, node in enumerate(nodes):
            for epnum in range(1, epcount + 1):
                reqid = f"{netnum}-{epnum}-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
                vm_uuid = str(uuid.uuid4())
                uuid_val = str(uuid.uuid4())
                vm_name = f"{mz}_{vm_uuid}"
                global vnic_name
                vnic_name = f"{mz}-{uuid_val}"
                vnic_names.append(vnic_name)

                vnic_template = template_data["virtualNicTemplate"].copy()

                vnic_template["metadata"]["annotations"]["RequestID"] = reqid
                vnic_template["metadata"]["namespace"] = ns
                vnic_template["metadata"]["name"] = vnic_name
                vnic_template["metadata"]["labels"]["OwnerNamespace"] = ns
                vnic_template["metadata"]["labels"]["ResourceGroup"] = resourceGroup
                vnic_template["metadata"]["labels"]["ResourceID"] = f"{mz}-{resourceID}"
                vnic_template["metadata"]["labels"]["VPCID"] = vpcid
                vnic_template["metadata"]["labels"]["vm_name"] = vm_name
                vnic_template["metadata"]["labels"]["InstanceID"] = vm_name
                vnic_template["metadata"]["labels"]["selflink"] = vnic_name
                vnic_template["spec"]["name"] = vnic_name
                vnic_template["spec"]["network"]["Name"] = nw
                vnic_template["spec"]["network"]["Namespace"] = ns
                vnic_template["spec"]["node"]["name"] = node.decode('utf-8')
                vnic_template["spec"]["floatingIP"] = f"192.121.{routerIndex}.{epnum}"
                vnic_template["spec"]["virtualMachine"]["Name"] = vm_name
                vnic_template["spec"]["virtualMachine"]["Namespace"] = ns
                vnic_template["spec"]["sgNames"] = [f"{sgName}"]

                verifydnic(node)
                if dnic:
                    commandtogetip = f"kubectl get node {node.decode('utf-8')} -o yaml"
                    command_output = run_command_strip(commandtogetip)
                    yaml_output = yaml.safe_load(command_output)
                    if yaml_output is None:
                        print("Unable to fetch the node yaml, This is None. So TunnelEndpointIP will not be added!")
                        continue
                    else:
                        nics_json = yaml_output['metadata']['annotations']['genctl.nics']
                        nics_list = json.loads(nics_json)
                        if nics_list:
                            for j, nic in enumerate(nics_list):
                                tunnelendpoint_ip = nics_list[j]['TunnelEndpointIP']
                                print(f"TunnelEndpointIP for NumaNode {j}/{node} is - {tunnelendpoint_ip}")
                                vnic_template["spec"]["tunnelEndpointIP"] = tunnelendpoint_ip
                        else:
                            print_red(f"TunnelEndpointIP not found for NIC {i}")

                applying(vnic_template)

                fipcount += 1


    # print_green(f"VNIC names - {vnic_names}")

#----------------------------------------------------------------------------------------
#   LB (Load Balancer) Files
#----------------------------------------------------------------------------------------

def create_lb():
    if loadbalancer in ["yes", "y"]:


        print_green("\nCreating LBs (Load Balancer)")

        global lb_name
        global lb_pool_name
        global lb_listener_name
        lb_name = f"{mz}-{str(uuid.uuid4())}"
        lb_pool_name = f"{mz}-{str(uuid.uuid4())}"
        lb_listener_name = f"{mz}-{str(uuid.uuid4())}"

        lb_template = template_data["loadBalancerTemplate"].copy()

        lb_template["metadata"]["namespace"] = ns
        lb_template["metadata"]["name"] = lb_name
        lb_template["spec"]["vpcid"] = vpcid
        lb_template["metadata"]["labels"]["VPCID"] = vpcid
        lb_template["spec"]["ipv4"] = generate_serviceGatewayIP(routerIndex)

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
    nodes = run_command("kubectl -n genctl get nodes --show-labels | grep compute | awk '{print $1}'").split()
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

    def generate_random_mountpath():
        chars = string.ascii_lowercase + string.digits + '_'
        random_string = ''.join(random.choice(chars) for _ in range(36))
        return f"/b{random_string[:8]}_{random_string[8:12]}_{random_string[12:16]}_{random_string[16:20]}_{random_string[20:]}"

    print_green("\nCreating SMTs")

    nodes = run_command("kubectl -n genctl get nodes --show-labels | grep compute | awk '{print $1}'").split()


    global smt_names
    smt_names = []


    for i, node in enumerate(nodes):

        smt_name = f"{mz}-{str(uuid.uuid4())}"
        smt_names.append(smt_name)
        eVPNprefixValue = f"23.{routerIndex}.{i}.0/24"

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

    nodes = run_command("kubectl -n genctl get nodes --show-labels | grep compute | awk '{print $1}'").split()

    for i, node in enumerate(nodes):

        global vni_name
        vni_name = f"{mz}-{str(uuid.uuid4())}"
        primaryrip_name = f"{mz}-{str(uuid.uuid4())}"


        vni_template = template_data["virtualNetworkInterfaceTemplate"].copy()

        vni_template["metadata"]["namespace"] = ns
        vni_template["metadata"]["name"] = vni_names[i]
        vni_template["metadata"]["uid"] = vni_uuids[i]
        vni_template["metadata"]["labels"]["VPCID"] = vpcid
        vni_template["spec"]["networkName"] = nw
        vni_template["spec"]["primaryReservedIPName"] = rip_names[i]
        # secondary_ips = [
        #     f"{rip_names[i+1]}"
        # ]s
        # vni_template["spec"]["secondaryIP"] = secondary_ips
        vni_template["spec"]["target"]["name"] = smt_names[i]
        vni_template["spec"]["target"]["type"] = "ShareMountTarget"
        vni_template["spec"]["securityGroupNames"] = [f"{sgName}"]

        applying(vni_template)


#----------------------------------------------------------------------------------------
#   Network Endpoints (NEPs)
#----------------------------------------------------------------------------------------


nif_names = []
nep_data = []

def create_networkEndpoint():
    global nif_names, nep_data  # Declare that these variables are global

    print_green("\nCreating Network Endpoints")

    nodes = run_command("kubectl -n genctl get nodes --show-labels | grep compute | awk '{print $1}'").split()

    nif_names = []

    for i in range(len(nodes)):
        nif_name = f"{mz}-{str(uuid.uuid4())}"
        nif_names.append(nif_name)

    for i, node in enumerate(nodes):
        nep_name = f"{mz}-{str(uuid.uuid4())}"
        nep_uuid = str(uuid.uuid4())

        nep_template = template_data["networkEndpointTemplate"].copy()

        nep_template["metadata"]["namespace"] = ns
        nep_template["metadata"]["name"] = nep_name
        nep_template["metadata"]["uid"] = nep_uuid
        nep_template["metadata"]["labels"]["VPCID"] = vpcid
        nep_template["status"]["vpcid"] = vpcid
        nep_template["spec"]["networkname"] = nw
        nep_template["spec"]["networkInterfaceNames"] = [nif_names[i]]  # Use the corresponding nif_name
        nep_template["spec"]["virtualNetworkInterface"] = vni_name

        nep_data.append({"name": nep_name, "uuid": nep_uuid})  # Store NEP data

        applying(nep_template)

#----------------------------------------------------------------------------------------
#   Network Interface (NIFs)
#----------------------------------------------------------------------------------------
def create_networkInterface():
    global nif_names, nep_data  # Declare that these variables are global

    print_green("\nCreating Network Interface")

    nodes = run_command("kubectl -n genctl get nodes --show-labels | grep compute | awk '{print $1}'").split()

    for i, node in enumerate(nodes):
        nif_name = nif_names[i]  # Use the nif_name generated earlier
        nif_uuid = str(uuid.uuid4())

        nep_data_item = nep_data[i]  # Get the corresponding NEP data

        nif_template = template_data["networkInterfaceTemplate"].copy()

        nif_template["metadata"]["namespace"] = ns
        nif_template["metadata"]["name"] = nif_name
        nif_template["metadata"]["uid"] = nif_uuid
        nif_template["metadata"]["ownerReferences"][0]["name"] = nep_data_item["name"]
        nif_template["metadata"]["ownerReferences"][0]["uid"] = nep_data_item["uuid"]
        nif_template["metadata"]["labels"]["OwnerNamespace"] = ns
        nif_template["metadata"]["labels"]["ResourceGroup"] = resourceGroup
        nif_template["metadata"]["labels"]["VPCID"] = vpcid
        nif_template["spec"]["vpcid"] = vpcid
        nif_template["spec"]["virtualNetworkInterface"] = vni_name
        nif_template["spec"]["nodeName"] = node.decode('utf-8')

        applying(nif_template)







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

    # Optional Loadbalancers with -lb flag
    "Loadbalancer": create_lb,
    "Lb Pool": create_lb_pool,
    "Lb Pool Members": create_lb_pool_members,
    "Lb Listeners": create_lb_listeners
}

all_resource_functions = {
    # Default resources
    "Router": create_router,
    "Routing Table": create_routing_table,
    "Ingress Routing Table": create_ingress_routing_table,
    "Security Groups": create_security_groups,
    "Nacls": create_nacls,
    "Networks": create_networks,
    "Foreign Networks": create_foreign_networks,
    "Vnics": create_vnics,

    # Optional resources with -vni flag
    "ReservedIp": create_reserved_ip,
    "Share Mount Targer": create_smt,
    "Virtual Network Interface": create_vni,

    # Uncomment these to create MANUALLY
    # "Network Endpoint": create_networkEndpoint,  #Ignoring for now as we are creating VNICs already which will take care of these
    # "Network Interface": create_networkInterface, #Ignoring for now as we are creating VNICs already which will take care of these

    # Optional Loadbalancers with -lb flag
    "Loadbalancer": create_lb,
    "Lb Pool": create_lb_pool,
    "Lb Pool Members": create_lb_pool_members,
    "Lb Listeners": create_lb_listeners
}

#---------------------------------------------------------------------------------------------------
def applyResources(saveyaml, routerIndex, stop_at_resource=None):
    #Setting the variables as global for access
    global rName
    global vpcid
    global rtrTableName
    global ingressRTName
    global resourceGroup
    global resourceID
    global rPrefix
    global nws
    global naclName
    global sgName
    global fnw_prefix

    routerIndex = routerIndex
    rPrefix = "r007"
    rName = f"{rPrefix}-{str(uuid.uuid4())}"
    vpcid = rName
    reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    sgName = ""
    naclName = ""
    rtrTableName = f"{rPrefix}-{str(uuid.uuid4())}"
    ingressRTName = f"{rPrefix}-{str(uuid.uuid4())}"
    resourceGroup = "fakedata119e4a61a3a015eb6d44ebbb"
    resourceID = "1e749755-119e-4a61-a3a0-15eb6d44ebbb"
    fnw_prefix = rPrefix
    nws = []


    def writeYaml(saveyaml, yaml_str, template):
        if saveyaml:
            namespace, kind, idName = extract_metadata(template)

            if not os.path.exists(f"./{vpcid}"):
                os.makedirs(f"./{vpcid}")
            os.chdir(f"./{vpcid}")

            resources_yaml = open(f"{kind}_{idName}.yaml", "w")
            resources_yaml.write(yaml_str)
            resources_yaml.close()
            os.chdir("..")

    print(f"\nnwcount: {nwcount}, epcount: {epcount}, ns: {ns}, mz: {mz}\n")

    #Opening the file to track the applied resources along with namespace
    applied_resources_file = open("applied_resources.txt", "a")
    applied_resources_file.write("\n")


    global applying

    def applying(template):
        if not doapply:
            yaml_str = yaml.dump(template, default_flow_style=False)
            namespace, kind, idName = extract_metadata(template)
            formatted_string = f"{namespace}, {kind}, {idName} - CREATED YAMLs, NOT APPLIED"
            applied_resources_file.write(formatted_string + "\n")

            if not os.path.exists(f"./{vpcid}"):
                os.makedirs(f"./{vpcid}")
            os.chdir(f"./{vpcid}")

            resources_yaml = open(f"{kind}_{idName}.yaml", "w")
            resources_yaml.write(yaml_str)
            resources_yaml.close()
            os.chdir("..")
        else:
            yaml_str = yaml.dump(template, default_flow_style=False)
            kubectl_apply_command = f"kubectl apply -f - <<EOF\n{yaml_str}\nEOF"
            namespace, kind, idName = extract_metadata(template)
            apply(kubectl_apply_command, kind)
            formatted_string = f"{namespace}, {kind}, {idName}"
            applied_resources_file.write(formatted_string + "\n")
            kubectl_check(namespace, kind, idName, yaml_str)
            writeYaml(saveyaml, yaml_str, template)


    #------------------------------------------
    # APPLYING ALL THE RESOURCES with UNTILL
    # ------------------------------------------
    for resource, func in default_resource_functions.items():
        if stop_at_resource and resource.lower() == stop_at_resource.lower():
            func() #Creates until the mentioned resource
            print(f"Stopped at {resource}. Resources until here have been applied.")
            return
        func() # This function creates all the DEFAULT resources in order

        #Done creating the resources

    applied_resources_file.close()


    print("------- The resources in this SET are applied  -------")

    create_shell_scripts(vpcid, allres, loadbalancer, doapply)




def applyAllResources(saveyaml, routerIndex, stop_at_resource=None ):
    #Setting the variables as global for access
    global rName
    global vpcid
    global rtrTableName
    global ingressRTName
    global resourceGroup
    global resourceID
    global rPrefix
    global nws
    global naclName
    global sgName
    global fnw_prefix
    routerIndex = routerIndex
    rPrefix = "r007"
    rName = f"{rPrefix}-{str(uuid.uuid4())}"
    vpcid = rName
    reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    sgName = ""
    naclName = ""
    rtrTableName = f"{rPrefix}-{str(uuid.uuid4())}"
    ingressRTName = f"{rPrefix}-{str(uuid.uuid4())}"
    resourceGroup = "fakedata119e4a61a3a015eb6d44ebbb"
    resourceID = "1e749755-119e-4a61-a3a0-15eb6d44ebbb"
    fnw_prefix = rPrefix
    nws = []

    print(f"\nnwcount: {nwcount}, epcount: {epcount}, ns: {ns}, mz: {mz}\n")


    def writeYaml(saveyaml, yaml_str, template):
        if saveyaml:
            namespace, kind, idName = extract_metadata(template)

            if not os.path.exists(f"./{vpcid}"):
                os.makedirs(f"./{vpcid}")
            os.chdir(f"./{vpcid}")

            resources_yaml = open(f"{kind}_{idName}.yaml", "w")
            resources_yaml.write(yaml_str)
            resources_yaml.close()
            os.chdir("..")
    #Opening the file to track the applied resources along with namespace
    applied_resources_file = open("applied_resources.txt", "a")
    applied_resources_file.write("\n")


    global applying

    def applying(template):
        if not doapply:
            yaml_str = yaml.dump(template, default_flow_style=False)
            namespace, kind, idName = extract_metadata(template)
            formatted_string = f"{namespace}, {kind}, {idName} - CREATED YAMLs, NOT APPLIED"
            applied_resources_file.write(formatted_string + "\n")

            if not os.path.exists(f"./{vpcid}"):
                os.makedirs(f"./{vpcid}")
            os.chdir(f"./{vpcid}")

            resources_yaml = open(f"{kind}_{idName}.yaml", "w")
            resources_yaml.write(yaml_str)
            resources_yaml.close()
            os.chdir("..")
        else:
            yaml_str = yaml.dump(template, default_flow_style=False)
            kubectl_apply_command = f"kubectl apply -f - <<EOF\n{yaml_str}\nEOF"
            namespace, kind, idName = extract_metadata(template)
            apply(kubectl_apply_command, kind)
            formatted_string = f"{namespace}, {kind}, {idName}"
            applied_resources_file.write(formatted_string + "\n")
            kubectl_check(namespace, kind, idName, yaml_str)
            writeYaml(saveyaml, yaml_str, template)


    #------------------------------------------
    # APPLYING THE RESOURCE
    # ------------------------------------------
    for resource, func in all_resource_functions.items():
        if stop_at_resource and resource.lower() == stop_at_resource.lower():
            func() #Creates until the mentioned resource
            print(f"Stopped at {resource}. Resources until here have been applied.")
            return
        func() # This function creates ALL the resources in order

    applied_resources_file.close()


    create_shell_scripts(vpcid, allres, loadbalancer, doapply)



def applySpecificResource(resource_type):

    #Setting the variables as global for access
    global rName
    global vpcid
    global rtrTableName
    global ingressRTName
    global resourceGroup
    global resourceID
    global rPrefix
    global nws
    global naclName
    global sgName
    global fnw_prefix
    rPrefix = "r007"
    rName = f"{rPrefix}-{str(uuid.uuid4())}"
    vpcid = rName
    reqid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    sgName = ""
    naclName = ""
    rtrTableName = f"{rPrefix}-{str(uuid.uuid4())}"
    ingressRTName = f"{rPrefix}-{str(uuid.uuid4())}"
    resourceGroup = "fakedata119e4a61a3a015eb6d44ebbb"
    resourceID = "1e749755-119e-4a61-a3a0-15eb6d44ebbb"
    fnw_prefix = rPrefix
    nws = []

    print(f"\nnwcount: {nwcount}, epcount: {epcount}, ns: {ns}, mz: {mz}\n")

    #Opening the file to track the applied resources along with namespace
    applied_resources_file = open("applied_resources.txt", "a")
    applied_resources_file.write("\n")


    global applying

    def applying(template):
        yaml_str = yaml.dump(template, default_flow_style=False)
        kubectl_apply_command = f"kubectl apply -f - <<EOF\n{yaml_str}\nEOF"
        namespace, kind, idName = extract_metadata(template)
        apply(kubectl_apply_command, kind)
        formatted_string = f"{namespace}, {kind}, {idName}"
        applied_resources_file.write(formatted_string + "\n")
        kubectl_check(namespace, kind, idName, yaml_str)

    #------------------------------------------
    # APPLYING THE SPECIFIC RESOURCE
    # ------------------------------------------
    all_resource_functions[resource_type]()

    applied_resources_file.close()


#----------------------------------------APPLY--------------------------------------------------------




def parse_arguments():
    parser = argparse.ArgumentParser(description="Script to create objects for a router, networks, and endpoints in a cloud environment.")
    parser.add_argument('action', choices=['create', 'delete', 'c', 'd', 'm', 'manipulate', 'get', 'g'], help="Specify whether to apply or delete resources. Default is Apply")
    parser.add_argument('-e', '--environment', choices=['pok', 've'], default='ve', help="Specify the environment (pok or ve). Default is VE")
    parser.add_argument('-ns', '--namespace', default='netobjs', help="Specify the NAMESPACE for Creation/Deletion. Default is \"netobjs\"", dest="namespace")
    parser.add_argument('-nc', '--networkcount', type=int, default=1, help="Specify the number of networks. (For Creation only)")
    parser.add_argument('-ec', '--endpointcount', type=int, default=1, help="Specify the number of endpoints. (For Creation only)")
    parser.add_argument('-ripc', '--reservedipcount', type=int, default=1, help="Specify the number of Reserved IPs to be created. (For Creation only & requires -vni flag)", dest="ripcount")
    parser.add_argument('-n', '--num', type=int, default=1, help="Specify the number of VPCs to create (Router sets). (For Creation only)", dest="sets")
    parser.add_argument('-lb', '--loadbalancer', action='store_true', help="Specify whether to apply load balancers (default is no). (For Creation only)")
    parser.add_argument('-ut', '--until', default=None, choices=[key.lower() for key in all_resource_functions.keys()], help="Specify the resource type to stop at during creation. (For Creation only)")
    parser.add_argument('-dff', '--deletefromfile', action='store_true', help="Specify if you want to delete the resources which are applied now. Uses applied_resources.txt file which can be customised as per your needs. (For Deletion only)", dest="delcurr")
    parser.add_argument('-a', '--apply', action='store_true', help="Specify whether to save the resources in YAML format without applying them. (For Creation only)", dest="doapply")
    parser.add_argument('-sy', '--saveyaml', action='store_true', help="Specify whether to save the Applied YAML format for further use or debugging. (For Creation only)", dest="saveyaml")
    parser.add_argument('-vni', '--vniresources', action='store_true', help="Specify if you want to apply all the resources. i.e - reservedIp VNI networkInterface and networkEndpoint will be created manually, VNIC will NOT be created. (For Creation only)", dest="allres")
    parser.add_argument('-sn', '--specificnode', nargs='+', help="Specify the name of the node to create VNIC resources on. (For Creation only)", dest="specificnode")
    parser.add_argument('-en', '--excludenode', nargs='+', help="Specify the name of the node to exclude from VNIC creation. (For Creation only)", dest="excludenode")
    args = parser.parse_args()
    return args




#MAIN (CREATE/DELETE) FUNCTIONS

def createResources(namespace, specificResource=None):
    args = parse_arguments()

    env = args.environment
    global mz
    try:
        if env == "pok":
            region_file = "/etc/genesis/region"
            region_contents = subprocess.check_output(["cat", region_file]).decode('utf-8')
            mz_match = re.search(r'/(\d+)mzone', region_contents)
            if mz_match:
                mz = mz_match.group(1)
            else:
                print("Error: MZONE value not found in", region_file)
                sys.exit(1)
        elif env == "ve":
            region_file = "/etc/genesis/region"
            region_contents = subprocess.check_output(["cat", region_file]).decode('utf-8')
            mz = ''.join(re.findall(r'\d+', region_contents))
        else:
            print("Please specify the environment as 'pok' or 've'")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print_red(f"Could not fetch the MZONE value: {e.output.decode('utf-8')}")
        usr_mz_input = input("So plesae enter the MZONE value (4 digit alphanumeric): ")
        mz = str(usr_mz_input)

    mz = mz[:4]
    if len(mz) < 4:
        mz = "0" + mz

    print(f"The set MZONE value is: {mz}")
    mz = mz[:4]

    # Taking in the SET count (Number of Router sets).
    global setCount
    global routerIndex
    global loadbalancer
    global nwcount
    global epcount
    global ripcount
    global ns
    global saveyaml
    global doapply
    global allres
    global specificnode
    global excludenode


    ns = namespace
    setCount = args.sets
    nwcount = args.networkcount
    epcount = args.endpointcount
    ripcount = args.ripcount
    saveyaml = args.saveyaml
    allres = args.allres
    doapply = args.doapply
    specificnode = args.specificnode
    excludenode = args.excludenode


    # Flag to apply the LoadBalancers or not
    loadbalancer = "yes" if args.loadbalancer else "no"

    action = "yes" if args.action.lower() in ['create', 'c'] else "no"
    manipulate = "yes" if args.action.lower() in ['manipulate', 'm'] else "no"



    # LOADING TEMPLATE DATA
    global template_data
    def load_template_data():
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        template_path = os.path.join(script_dir, "template.json")

        try:
            with open(template_path, "r") as json_file:
                template_data = json.load(json_file)
            return template_data
        except FileNotFoundError:
            print("Template Data not found / path not configured properly. Please correct it before proceeding")
            sys.exit(1)

    # Load the template data
    template_data = load_template_data()

    #Resource Application starts here
    if action in ['yes']:
        if allres:
            start_time = time.time()
            for routerIndex in range(1, setCount + 1):
                print_green(f"--------  Creating VPC Number {routerIndex} / {setCount} --------")
                applyAllResources(saveyaml, routerIndex,  stop_at_resource=args.until)


            if doapply:
                print("-------      ALL THE RESOURCES ARE APPLIED        -------")
                time_taken(start_time)
        else:
            start_time = time.time()
            for routerIndex in range(1, setCount + 1):
                print_green(f"--------  Creating VPC Number {routerIndex} / {setCount} --------")
                applyResources(saveyaml, routerIndex, stop_at_resource=args.until)
            if doapply:
                print("-------      ALL THE RESOURCES ARE APPLIED        -------")
                time_taken(start_time)


    if manipulate in ['yes']:
        if specificResource:
            applySpecificResource(specificResource)

# APPLY DONE



def getResources(namespace):
    kinds = ["virtualnic", "networkinterface", "networkendpoint", "endpointgateway", "lbpoolmember", "lblistener", "lbpool", "loadbalancer", "virtualnetworkinterface","sharemounttarget", "reservedip", "ipaddress", "network", "securitygroup", "networkacl", "routingtable", "router"]
    ns = namespace
    print_green(f"Running 'Kubectl get' in namespace '{ns.capitalize()}': \n")
    for kind in kinds:
        numbers = run_command(f"kubectl -n {ns} get {kind} --no-headers -o custom-columns=:metadata.name | wc -l")

        print_green(f"\nFound {numbers.decode('utf-8')} {kind}s: ")


        # Get the list of objects
        result = subprocess.run([f"kubectl -n {ns} get {kind} --no-headers -o custom-columns=:metadata.name"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            objects = result.stdout.splitlines()

            # Print each object of that kind
            for obj in objects:
                obj = obj.decode('utf-8')
                print(obj)
        else:
            print_red(f"Failed to get {kind}s. Error: {result.stderr}")


# This deletes all the resources from the given namespace
def deleteResources(namespace):
    kinds = ["virtualnic", "networkinterface", "networkendpoint", "lbpoolmember", "lblistener", "lbpool", "loadbalancer", "virtualnetworkinterface","sharemounttarget", "reservedip", "ipaddress", "network", "securitygroup", "networkacl", "routingtable", "router"]
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
    if os.path.exists("./applied_resources.txt"):
        choice = input("Do you want to delete the 'applied_resources.txt/.yaml' files? (y/n): ")
        if choice.lower() in ['yes', 'y']:
            if os.path.exists("./applied_resources.txt"):
                run_command("rm ./applied_resources.txt")
            if os.path.exists("./applied_resources.yaml"):
                run_command("rm ./applied_resources.yaml")
        else:
            print("applied_resources files are retained")



# This uses applied_resources.txt file to delete resources. You can modify it as per your requirement
def deleteCurrentResources(file_path):

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


def getStatus(ns):
    def get_virtual_nics_from_file(ns, file_path='applied_resources.txt'):
        virtual_nics = []
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if f'{ns}, VirtualNic, ' in line:
                        virtual_nic_name = line.split(', ')[2].strip()
                        virtual_nics.append(virtual_nic_name)
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
        return virtual_nics

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

    def get_interface_name(vnic, ns):
        try:
            command = ["kubectl", "describe", "virtualnic", vnic, "-n", ns]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            if result.returncode != 0:
                print(f"Error occurred: {result.stderr}")
                return None

            # Extract the interface name using grep and awk
            grep_command = "grep 'Network Interface:' -A 1 | grep 'Name:' | awk '{print $2}'"
            grep_result = subprocess.run(grep_command, input=result.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

            if grep_result.returncode != 0:
                print(f"Error occurred: {grep_result.stderr}")
                return None

            return grep_result.stdout.strip()

        except subprocess.CalledProcessError as e:
            print(f"Error occurred while getting interface name for {vnic}: {e.stderr}")
            return None

    def check_interface_ready(interface_name, ns):
        try:
            kubectl_command = ["kubectl", "describe", "networkinterface", interface_name, "-n", ns]
            result = subprocess.run(kubectl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            grep_command_ready = ["grep", "Ready:"]
            grep_result_ready = subprocess.run(grep_command_ready, input=result.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            grep_command_port = ["grep", "Port ID:"]
            grep_result_port = subprocess.run(grep_command_port, input=result.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            is_ready = False
            local_port_id = None

            if grep_result_ready.stdout.strip():
                status_line = grep_result_ready.stdout.strip()
                is_ready = status_line.split(':')[1].strip().lower() == 'true'

            if grep_result_port.stdout.strip():
                port_line = grep_result_port.stdout.strip()
                local_port_id = port_line.split(':')[1].strip()

            return is_ready, local_port_id
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while checking ready status for {interface_name}: {e.stderr}")
            return False, None

    print_green(f"Fetching Virtual NICs in {ns} namespace..")
    virtual_nics = get_virtual_nics(ns)
    print_green(f"Total number of Virtual NICs found : {len(virtual_nics)}")

    if len(virtual_nics) == 0 or virtual_nics == ['']:
        print_green("No Virtual NICs found.")
        return
    else:
        print(f"VNICS names in {ns} namespace :{virtual_nics}\n ")

    for vnic in virtual_nics:
        print_green(f"Processing VNIC: {vnic}")

        interface_name = get_interface_name(vnic, ns)
        if not interface_name:
            print(f"Failed to get interface name for {vnic}")
            continue

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


#End of the script