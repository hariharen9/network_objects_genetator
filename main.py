#!/usr/bin/env python3

######################################################################
#
# This script can be used to :
# Create network resources like Routers, SGs, Networks, VNICs, LBs etc. (create/c)
# Delete network resources from the specified namespace (delete/d)
# Restart a Manager/All the managers (restart/r)
# Get logs from the existing managers/Restared manager, Also gets the cache information from them. (getlogs/gl)
# Get Cache information directly by restarting all the managers (getcache/gc)
# Mimic the production environment by randomly create/update/delete various resources (manipulate/m)
#
# You can specify network count, endpoint count, Number of sets of routers, Save the applied YAML files for debugging, Loadbalancers are optional and can stop at any particular resource
# If not specified, it will use default values.
#
# usage:
# Make the main.py script executable or use the python3 keyboard before the execuion of the file.
#
# ./main.py -a create/delete/restart/getLogs/getcache/manipulate

######################################################################

import argparse
import resourceGen as rg
import cachetime as ct
import manipulation as man


actions = {
    'create': rg.createResources,
    'c': rg.createResources,
    'delete': rg.deleteResources,
    'd': rg.deleteResources,
    'get': rg.getResources,
    'g': rg.getResources,
    'restart': ct.delmanager,
    'r': ct.delmanager,
    'getlogs': ct.getlogs,
    'gl': ct.getlogs,
    'getcache': ct.restart_all_gc,
    'gc': ct.restart_all_gc,
    'm': man.manipulate,
    'manipulate': man.manipulate,
    'gs': rg.getStatus,
    'getstatus': rg.getStatus
}

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="CREATE(c) - Script to create Network objects in a cloud environment.\n DELETE(d) - Deletes the created objects\n RESTART(r) - Restarts a POD and makes it ready to fetch the logs from. \n GETLOGS(l) - To Extract the Synchronization logs from the New POD"
    )
    parser.add_argument('action', choices=actions.keys(), help="Specify whether to Create/Delete resources or Restart/GetLogs/GetCache from the POD(s). Default is Resource Creation")
    parser.add_argument('-e', '--environment', choices=['pok', 've'], default='ve', help="Specify the environment (pok or ve). Default is VE")
    parser.add_argument('-ns', '--namespace', default='netobjs', help="Specify the NAMESPACE for Creation/Deletion. Default is \"netobjs\"", dest="namespace")
    parser.add_argument('-nc', '--networkcount', type=int, default=1, help="Specify the number of networks. (For Creation only)")
    parser.add_argument('-ec', '--endpointcount', type=int, default=1, help="Specify the number of endpoints. (For Creation only)")
    parser.add_argument('-ripc', '--reservedipcount', type=int, default=1, help="Specify the number of Reserved IPs to be created. (For Creation only & requires -vni flag)", dest="ripcount")
    parser.add_argument('-n', '--num', type=int, default=1, help="Specify the number of VPCs to create (Router sets). (For Creation only)", dest="sets")
    parser.add_argument('-lb', '--loadbalancer', action='store_true', help="Specify whether to apply load balancers (default is no). (For Creation only)")
    parser.add_argument('-ut', '--until', default=None, choices=[key.lower() for key in rg.all_resource_functions.keys()], help="Specify the resource type to stop at during creation. (For Creation only)")
    parser.add_argument('-sy', '--saveyaml', action='store_true', help="Specify whether to save the Applied YAML format for further use or debugging. (For Creation only)", dest="saveyaml")
    parser.add_argument('-a', '--apply', action='store_true', help="Specify whether to save the resources in YAML format without applying them. (For Creation only)", dest="apply")
    parser.add_argument('-dff', '--deletefromfile', action='store_true', help="Specify if you want to delete the resources which are applied now. Uses applied_resources.txt file which can be customised as per your needs. (For Deletion only)", dest="delcurr")
    parser.add_argument('-cn', '--containername', default='fabcon-manager', choices=['fabcon-manager', 'network-manager'], help="Specify the container name to restart/getLogs, Default is \"fabcon-manager\". (For RESTART only)", dest="containername")
    parser.add_argument('-vni', '--vniresources', action='store_true', help="Specify if you want to apply all the resources. i.e - reservedIp VNI networkInterface and networkEndpoint will be created manually, VNIC will NOT be created. (For Creation only)", dest="allres")
    parser.add_argument('-sn', '--specificnode', nargs='+', help="Specify the name of the node to create VNIC resources on. (For Creation only)", dest="specificnode")
    parser.add_argument('-en', '--excludenode', nargs='+', help="Specify the name of the node to exclude from VNIC creation. (For Creation only)", dest="excludenode")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_arguments()
    ns = args.namespace
    delete_curr = args.delcurr
    if args.action in actions:
        action_function = actions[args.action]

        if args.action in ['create', 'c', 'get', 'g', 'gs', 'getstatus']:
            action_function(ns)  # NAMESPACE HERE FOR CREATION/DELETION
        if args.action in ['delete', 'd']:
            if delete_curr:
                rg.deleteCurrentResources("applied_resources.txt")
            else:
                action_function(ns)  # NAMESPACE HERE FOR CREATION/DELETION

        elif args.action in ['restart', 'r', 'getlogs', 'gl', 'getcache', 'gc']:
            ct.setup()
            action_function()
        elif args.action in ['m', 'manipulate']:
            action_function()

    else:
        print("Please choose the correct ACTION to perform, Use \"--help\" for more details")
