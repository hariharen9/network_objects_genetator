import subprocess
import threading
import time
import random
import resourceGen as rg
import sys

def print_red(text):
    print("\033[91m" + str(text) + "\033[0m")

def print_green(text):
    print("\033[92m" + str(text) + "\033[0m")

def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if result.returncode != 0:
        print(f"{result.stderr.decode('utf-8')}")
    return result.stdout

def get_random_valid_line(lines):
    while lines:
        line = random.choice(lines)
        parts = line.strip().split(", ")
        if len(parts) == 3:
            return parts
    return None

def update_resource(namespace, kind, name):
    update_command = f'kubectl label {kind.lower()} -n {namespace} {name} app=updated-app --overwrite=true'
    print_green(f"Updating {kind} in namespace - {namespace} with name - {name}")
    result = run_command(update_command)
    if result:
        print(result)

def delete_resource(namespace, kind, name):
    delete_command = f'kubectl delete {kind.lower()} -n {namespace} {name} --wait=false'
    print_red(f"Deleting {kind} in namespace - {namespace} with name - {name}")
    result = run_command(delete_command)
    if result:
        print(result)

resource_functions = {
    "Router": rg.create_router,
    "Routing Table": rg.create_routing_table,
    "Ingress Routing Table": rg.create_ingress_routing_table,
    "Security Groups": rg.create_security_groups,
    "Nacls": rg.create_nacls,
    "Networks": rg.create_networks,
    "Foreign Networks": rg.create_foreign_networks,
}

def create_resources(thread_id):
    while True:
        resource_type = random.choice(list(resource_functions.keys()))
        rg.createResources("manipulation", specificResource=resource_type)

        sleep_duration = random.randint(1, 10)
        print(f"Thread-{thread_id}:\tSleeping for {sleep_duration} seconds before the next create action...")
        time.sleep(sleep_duration)

def update_resources(thread_id):
    while True:
        with open("./applied_resources.txt", "r") as file:
            lines = file.readlines()
            if lines:
                parts = get_random_valid_line(lines)
                if parts:
                    namespace, kind, name = parts
                    update_resource(namespace, kind, name)
                else:
                    print(f"Thread-{thread_id}:\tNo valid resources to update.")
            else:
                print(f"Thread-{thread_id}:\tNo resources to update. File is empty.")

        sleep_duration = random.randint(1, 10)
        print(f"Thread-{thread_id}:\tSleeping for {sleep_duration} seconds before the next update action...")
        time.sleep(sleep_duration)

def delete_resources(thread_id):
    while True:
        with open("./applied_resources.txt", "r") as file:
            lines = file.readlines()
            if lines:
                parts = get_random_valid_line(lines)
                if parts:
                    namespace, kind, name = parts
                    delete_resource(namespace, kind, name)
                else:
                    print(f"Thread-{thread_id}:\tNo valid resources to delete.")
            else:
                print(f"Thread-{thread_id}:\tNo resources to update. File is empty.")

        sleep_duration = random.randint(1, 10)
        print(f"Thread-{thread_id}:\tSleeping for {sleep_duration} seconds before the next delete action...")
        time.sleep(sleep_duration)


def manipulate():
    create_thread = threading.Thread(target=create_resources, args=(1,))
    update_thread = threading.Thread(target=update_resources, args=(2,))
    delete_thread = threading.Thread(target=delete_resources, args=(3,))

    create_thread.start()
    update_thread.start()
    delete_thread.start()

    create_thread.join()
    update_thread.join()
    delete_thread.join()

