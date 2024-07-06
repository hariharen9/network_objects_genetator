import argparse
import subprocess
import sys
import time
import os
import resourceGen as rg

#Helper Functions
def print_red(text):
    print("\033[91m" + str(text) + "\033[0m")
def print_green(text):
    print("\033[92m" + str(text) + "\033[0m")

def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if result.returncode != 0:
        print(f"{result.stderr.decode('utf-8')}")
    return result.stdout


def global_get_managers(namespace, container_name):

    command = f"kubectl get pods -n {namespace} | grep {container_name} > {container_name}.txt"
    run_command(command)
    with open(f'{container_name}.txt', 'r') as file:
        contents = file.read()
        print(contents)
    pod_names = []
    with open(f'{container_name}.txt', 'r') as file:
        lines = file.readlines()
        for line in lines:
            podName = line.split()[0]  # Extract the first element (pod name) from each line
            pod_names.append(podName)
        global number_of_pods
        number_of_pods = len(pod_names)
        print(f"Total number of {container_name}(s) are : {len(pod_names)}")
    return pod_names

def get_managers(namespace, container_name):

    command = f"kubectl get pods -n {namespace} | grep {container_name} > {container_name}.txt"
    run_command(command)
    with open(f'{container_name}.txt', 'r') as file:
        contents = file.read()
        print(contents)
    pod_names = []
    with open(f'{container_name}.txt', 'r') as file:
        lines = file.readlines()
        for line in lines:
            podName = line.split()[0]  # Extract the first element (pod name) from each line
            pod_names.append(podName)
    return pod_names


def restart_manager(namespace, pod_names):
    print_red("Deleting(Restarting) Managers..")
    print_green(pod_names)

    global restart_all
    restart_all = input("Do you want to restart all the pods? (yes/no): ").lower()

    if restart_all in ["yes", "y"]:
        for pod_name in pod_names:
            delete_command = f"kubectl delete pod {pod_name} -n {namespace}"
            run_command(delete_command)
            print(f"Restarted pod: {pod_name}")

    elif restart_all in ["no", "n"]:
        position = input("Which pod do you wanna delete [1, 2, ..]? : ")

        if not position.isdigit():
            print_red("Please choose a POD using the index")
            sys.exit(1)
        else:
            position = int(position)

        position = position - 1
        try:
            selected_pod = pod_names[position]
            ack = input(f"Delete the {selected_pod}? : ").lower()
            if ack in ["yes", "y", "s"]:
                delete_command = f"kubectl delete pod {selected_pod} -n {namespace}"
                run_command(delete_command)
                print(f"Restarted pod: {selected_pod}")
            else:
                print("Stopping the restart")
                sys.exit(1)
        except IndexError:
            print_red("Invalid pod index. Please choose a valid index.")
    else:
        print_red("Invalid input. Please enter 'yes(y)' or 'no(n)'.")
        sys.exit(1)


def extract_sync_messages(input_file_path, output_sync_file_path, pod_name):
    cache_found = False
    with open(input_file_path, 'r') as input_file, open(output_sync_file_path, 'w') as output_file:
        for line in input_file:

            if "Cache & Fabcon Synchronization" in line or '"MESSAGE":"Synchronized' in line:
                output_file.write(line)
                cache_found = True


        if not cache_found:
            output_file.write(f"The logs are stored in the {pod_name}.logs file, No Cache information was found now, try restarting the pods and try again")
    print_red(f"Logs from : {pod_name}")
    status = run_command(f"cat {output_sync_file_path}")
    print_green(status.decode('utf-8'))

def extract_logs(namespace, pod_names, container_name):
    print_green("Extracting logs..")
    print_green(pod_names)
    global extract_all
    extract_all = input("Do you want to get LOGS from all the pods? (yes/no): ").lower()

    # Create the 'logs_info' folder if it doesn't exist
    if not os.path.exists('logs_info'):
        os.makedirs('logs_info')

    if extract_all in ["yes", "y"]:
        for pod_name in pod_names:
            command = f"kubectl logs {pod_name} -n {namespace} -c {container_name} > logs_info/{pod_name}.logs"
            run_command(command)
            extract_sync_messages(f"logs_info/{pod_name}.logs", f"logs_info/CacheSync_time_of_{pod_name}.txt", pod_name)
    elif extract_all in ["no", "n"]:
        position = input("Which pod do you GET logs from [1, 2,..]? : ")
        if not position.isdigit():
            print_red("Please choose a POD using the index")
            sys.exit(1)
        else:
            position = int(position)
        position = position - 1
        try:
            selected_pod = pod_names[position]
            pod_name = selected_pod
            command = f"kubectl logs {pod_name} -n {namespace} -c {container_name} > logs_info/{pod_name}.logs"
            run_command(command)
            extract_sync_messages(f"logs_info/{pod_name}.logs", f"logs_info/CacheSync_time_of_{pod_name}.txt", pod_name)
        except IndexError:
            print_red("Invalid pod index. Please choose a valid index.")
    else:
        print_red("Invalid input. Please enter 'yes(y)' or 'no(n)'.")
        sys.exit(1)


def restart_and_extract_logs(namespace, pod_names, container_name):
    restart_manager(namespace, pod_names)
    time.sleep(10)
    if restart_all in ["no", "n"]:
        while True:
            new_pod_names = get_managers(namespace, container_name)

            if len(new_pod_names) == number_of_pods:
                print("All NEW pods are up and running.")
                break  # Exit the loop if all pods are up

            print("The pods are not ready yet, Waiting for 30 seconds...")
            time.sleep(30)

        print("Pods are up. Resuming further actions.")

        # Assign the result of set difference to new_pod_names
        new_pod_names = set(new_pod_names) - set(pod_names)

        if new_pod_names:
            new_pod_name = new_pod_names.pop()
            print_green(f"Pod restarted. New pod name: {new_pod_name}")
            # Update pod_names to include the new pod
            pod_names.append(new_pod_name)
        else:
            print_red("Unable to determine the new pod name after restart.")
        if not os.path.exists('logs_info'):
            os.makedirs('logs_info')
        wait_command = f"kubectl wait --for=condition=ready pod/{new_pod_name} -n {namespace} --timeout=300s"
        print_red("Waiting for the POD to achieve READY STATE")
        run_command(wait_command)
        command = f"kubectl logs {new_pod_name} -n {namespace} -c {container_name} > logs_info/{new_pod_name}.logs"

        run_command(command)

        extract_sync_messages(f"logs_info/{new_pod_name}.logs", f"logs_info/CacheSync_time_of_{new_pod_name}.txt", new_pod_name)

    elif restart_all in ["yes", "y"]:
        while True:
            new_pod_names = get_managers(namespace, container_name)

            if len(new_pod_names) == number_of_pods:
                print("All NEW pods are up and running.")
                break  # Exit the loop if all pods are up

            print("The pods are not ready yet, Waiting for 30 seconds...")
            time.sleep(30)

        print("Pods are up. Resuming further actions.")
        #Assign the result of set difference to new_pod_names
        new_pod_names = set(new_pod_names) - set(pod_names)

        if new_pod_names:
            for pod in new_pod_names:
                wait_command = f"kubectl wait --for=condition=ready pod/{pod} -n {namespace} --timeout=300s"
                print_green(f"Waiting for the POD:{pod} to achieve READY STATE")
                if not os.path.exists('logs_info'):
                    os.makedirs('logs_info')
                run_command(wait_command)
                command = f"kubectl logs {pod} -n {namespace} -c {container_name} > logs_info/{pod}.logs"

                run_command(command)

                extract_sync_messages(f"logs_info/{pod}.logs", f"logs_info/CacheSync_time_of_{pod}.txt", pod)


def restart_all_and_extract_logs(namespace, pod_names, container_name):
    print_red("Deleting(Restarting) Managers..")
    print_green(pod_names)
    for pod_name in pod_names:
        delete_command = f"kubectl delete pod {pod_name} -n {namespace}"
        run_command(delete_command)
        print(f"Restarted pod: {pod_name}")
    while True:
        new_pod_names = get_managers(namespace, container_name)

        if len(new_pod_names) == number_of_pods:
            print("All NEW pods are up and running.")
            break  # Exit the loop if all pods are up

        print("The pods are not ready yet, Waiting for 30 seconds...")
        time.sleep(30)

    print("Pods are up. Resuming further actions.")

    #Assign the result of set difference to new_pod_names
    new_pod_names = set(new_pod_names) - set(pod_names)

    if new_pod_names:
        for pod in new_pod_names:
            wait_command = f"kubectl wait --for=condition=ready pod/{pod} -n {namespace} --timeout=300s"
            print_green(f"Waiting for the POD:{pod} to achieve READY STATE")
            if not os.path.exists('logs_info'):
                os.makedirs('logs_info')
            run_command(wait_command)
            command = f"kubectl logs {pod} -n {namespace} -c {container_name} > logs_info/{pod}.logs"

            run_command(command)

            extract_sync_messages(f"logs_info/{pod}.logs", f"logs_info/CacheSync_time_of_{pod}.txt", pod)


def setup():
    def parse_arguments():
        parser = argparse.ArgumentParser(
            description="CREATE(c) - Script to create Network objects in a cloud environment.\n DELETE(d) - Deletes the created objects\n RESTART(r) - Restarts a POD and makes it ready to fetch the logs from. \n GETLOGS(l) - To Extract the Synchronization logs from the New POD"
        )
        parser.add_argument('action', choices=["r", "restart", "gl", "getlogs", "gc", "getcache"], help="Specify whether to Create/Delete resources or Restart/GetLogs/GetCache from the POD(s). Default is Resource Creation")
        parser.add_argument('-cn', '--containername', default='fabcon-manager', choices=['fabcon-manager', 'network-manager'], help="Specify the container name to restart/getLogs, Default is \"fabcon-manager\". (For RESTART only)", dest="containername")

        args = parser.parse_args()
        return args

    args = parse_arguments()
    global namespace
    global container_name
    namespace = "genctl"
    container_name = args.containername

    global pod_names
    pod_names = global_get_managers(namespace, container_name)



def delmanager():
    restart_manager(namespace, pod_names)

def getlogs():
    choice = input("Extract Logs from existing PODs(1) or Restart & Extract Logs(2)? : ")
    if choice == "1":
        extract_logs(namespace, pod_names, container_name)
    elif choice == "2":
        restart_and_extract_logs(namespace, pod_names, container_name)
    else:
        print('Please Choose the correct option using the INTEGERS')

def restart_all_gc():
    restart_all_and_extract_logs(namespace, pod_names, container_name)