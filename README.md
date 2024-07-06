# Network Objects Simulator

## Overview

These scripts can be used to create/delete/get/restart/getLogs/getcache/manipulate resources. This is an internal utility used to create test environment with network K8S objects.

## Actions :

1. Create network resources like Routers, Routing Tables, SGs, Networks, NACLs, VNICs, and LBs. (Create a VPC) `(create/c)`

>* There Is an `--vni` flag which will create resources for VNI Phase 1 FaaS ( Namely RIP, SMT & VNI)

2. Delete network resources from the specified namespace `(delete/d)`

>* Also, delete resources form the applied resources file with the `-dcr` flag, (Offers customizability).

3. Displays the resources from a particular namespace to ensure the creation has occurred. `(get/g)`

>* You can specify any namespace to get the objects that.

4. Restart a Manager/All the managers `(restart/r)`

>* You can choose to restart all the managers or individually pick them as per our choice.

5. Get logs from the existing managers/Restared manager, Also gets the cache information from them. `(getlogs/gl)`

>* You can choose to get logs from all the managers or individually pick them as per our choice.

6. Get Cache information directly by restarting all the managers `(getcache/gc)`

>* This will restart all the managers, wait till the new pods come up, wait till they achieve the ready state (i.e 2/2 in this case) and then saves the logs to a file and extracts the sync information from it and also saves this in a separate file.

7. Mimic the production environment by randomly create/update/delete various resources. This basic action takes place after a random sleep duration. `(manipulate/m)`

 You can specify network count, endpoint count, Number of sets of routers, Loadbalancers are optional and can stop at any particular resource. If not specified, it will use default values.

### FLAGS:


> `' a ' or ' action '` is __*REQUIRED*__  "Specify what action should take place. choices= (create/c, delete/d, manipulate/m, get/g, getlogs/gl, getcache/gc, restart/r)"

> Flag : `'-a', '--apply'`,  "Specify whether to directly apply the resources without yaml creation. (For Creation only)", dest="doapply"

> Flag : `'-n', '--num'`,  default=1,  "Specify the number of VPCs (Router Sets) to create. (For Creation only)"

> Flag : `'-e', '--environment'`,  "Specify the environment (pok or ve)"

> Flag : `'-ns', '--namespace'`, default='netobjs',  "Specify the NAMESPACE for Creation/Deletion.

> Flag : `'-nc', '--networkcount'`,  default=1,  "Specify the number of networks. (For Creation only)

> Flag : `'-ec', '--endpointcount'`,  default=1,  "Specify the number of endpoints. (For Creation only)"

> Flag : `'-ripc', '--reservedipcount'`, default=1,  "Specify the number of Reserved IPs to be created. (For Creation only & requires '-vni' flag)"

> Flag : `'-lb', '--loadbalancer'`,   "Specify whether to apply load balancers or not, Default is no. (For Creation only)"

> Flag : `'-ut', '--until'`, "Specify untill which resource you need to create and stop after that, E.G - `-ut 'Security Groups'` will Only create Router, RT, IngressRT and SG. Everthing after that will be ignored. (For Creation only)"

> Flag : `'-dff', '--deletefromfile'`,   "Specify if you want to delete the resources which are applied now. Uses  __applied_resources.txt file__ which can be customised as per your needs. (For Deletion only)"

> Flag : `'-sy', '--saveyaml'`, "Specify whether to save the Applied YAML format for further use or debugging, This will save all the YAMLs in a single file. (For Creation only)"

> Flag : `'-cn', '--containername'`,  "Specify from which container you need to get the data/ restart (EG: Fabcon-manager/Network-manager)"

> Flag : `'-vni', '--vniresources'`,  "Specify if you want to apply VNI Phase 1 FaaS resources. i.e - VNI, SMTs & RIPs (For Creation only)"

## Installation:

>The user will have to have these __5 files__ saved before execution. (Make sure these files are in the `same` directory)

#### 1. main.py

#### 2. resourceGen.py

#### 3. cachetime.py

#### 4. manipulation.py

#### 5. template.json

## Usage:
>Make the *main.py* script executable using `chmod +x` or use the `python3` keyword before the execuion of the file. This acts as the entry point for this tool.

### `./main.py create/delete/get/restart/getLogs/getcache/manipulate -optionalParams`

### Example usage -

>`./main.py c`
>will create 1 set of resources including Router, RT, SG, NACLS, Network, ForeignNetwork and VNIC
>
>`./main.py c -lb`
>will create the same resources as above along with LB, LBPool, LBPoolMembers, LBListeners
>
>`./main.py c -lb -s 3 -vni`
>Will create the same resources as above but it will create 3 sets of them, along with VNI, SMT and ReservedIPs
>
> `./main.py c -a -lb -s 3 -vni`
> Will create the same resources as above but it will directly apply the resources. The `-a` flag denotes *Apply*.
>
> `./main.py c -a -lb -s 3 -vni -sy`
> Will create the same resources as above but it will directly apply the resources and also the yamls and the shell scripts of them will be saved in respective folders
>
>`./main.py g` & `./main.py d` will get the resoueces and deletes the resources from the given Namespace respectively.

#### ( For opional params please check the Flags section in the [README.MD] or use `-h/--help` flag )

