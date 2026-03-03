import subprocess
import threading
import time
import random
import resourceGen as rg
import sys
from utils import *

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

def update_resources(thread_id, args, shutdown_event):
    while not shutdown_event.is_set():
        try:
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
        except FileNotFoundError:
            print(f"Thread-{thread_id}:\t'applied_resources.txt' not found. Skipping update.")


        sleep_duration = random.randint(1, 10)
        print(f"Thread-{thread_id}:\tSleeping for {sleep_duration} seconds before the next update action...")
        shutdown_event.wait(sleep_duration)

def delete_resources(thread_id, args, shutdown_event):
    while not shutdown_event.is_set():
        try:
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
        except FileNotFoundError:
            print(f"Thread-{thread_id}:\t'applied_resources.txt' not found. Skipping delete.")

        sleep_duration = random.randint(1, 10)
        print(f"Thread-{thread_id}:\tSleeping for {sleep_duration} seconds before the next delete action...")
        shutdown_event.wait(sleep_duration)


def manipulate(args):
    shutdown_event = threading.Event()
    print_green("Starting manipulation mode, It will keep updating and deleting resources randomly. Press Ctrl+C to stop gracefully.")

    threads = [
        threading.Thread(target=update_resources, args=(1, args, shutdown_event)),
        threading.Thread(target=delete_resources, args=(2, args, shutdown_event))
    ]

    for t in threads:
        t.start()

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print_yellow("\nShutdown signal received. Stopping worker threads gracefully...")
        shutdown_event.set()
    
    for t in threads:
        t.join()

    print_green("All manipulation threads have been stopped.")