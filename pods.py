import shlex
import subprocess
import json
import os
import shutil
import difflib
import re
import time
from utils import *

def get_pod_info():
    """
    Fetches and displays comprehensive status information for netsim manager pods.
    """
    namespace = "sim-ns"
    pod_to_image_map = {
        "core-manager": "core-manager",
        "net-manager": "net-manager",
        "edge-manager": "core-manager",
        "clean-manager": "nettool-manager"
    }
    target_managers = list(pod_to_image_map.keys())
    
    print_green(f"Fetching status for NetSim pods in namespace: {namespace}")

    try:
        get_names_command = f"kubectl get pods -n {namespace} -o=jsonpath='{{.items[*].metadata.name}}'"
        names_result = subprocess.run(get_names_command, shell=True, capture_output=True, text=True, check=True)
        all_pod_names = names_result.stdout.split()
    except subprocess.CalledProcessError as e:
        print_red(f"Error fetching pod names: {e.stderr}")
        return

    # Explicitly filter for target pod names for readability
    target_pod_names = []
    for name in all_pod_names:
        for manager in target_managers:
            if manager in name:
                target_pod_names.append(name)
                break
    
    if not target_pod_names:
        print_yellow("No running manager pods found.")
        return

    print_green(f"Found {len(target_pod_names)} manager pods. Fetching details...")

    try:
        pod_names_str = " ".join(target_pod_names)
        get_pods_command = f"kubectl get pods -n {namespace} {pod_names_str} -o json"
        pods_result = subprocess.run(get_pods_command, shell=True, capture_output=True, text=True, check=True)
        pods_data = json.loads(pods_result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print_red(f"Error fetching or parsing pod details: {e}")
        return

    found_pods_info = []

    for pod in pods_data.get("items", []):
        pod_name = pod.get("metadata", {}).get("name", "")
        
        # Extract basic info
        pod_status = pod.get("status", {}).get("phase", "Unknown")
        pod_ip = pod.get("status", {}).get("podIP", "N/A")
        node_name = pod.get("spec", {}).get("nodeName", "N/A")

        # Calculate ready status
        total_containers = len(pod.get("spec", {}).get("containers", []))
        ready_containers = 0
        if pod.get("status", {}).get("containerStatuses"):
            for cs in pod["status"]["containerStatuses"]:
                if cs.get("ready"):
                    ready_containers += 1
        ready_status = f"{ready_containers}/{total_containers}"

        # Find the correct image using an explicit loop for readability
        image_to_display = "N/A"
        expected_image_substring = None
        for pod_keyword, image_keyword in pod_to_image_map.items():
            if pod_keyword in pod_name:
                expected_image_substring = image_keyword
                break

        if expected_image_substring:
            for container in pod.get("spec", {}).get("containers", []):
                image = container.get("image", "")
                if "vault" not in image and expected_image_substring in image:
                    image_to_display = image
                    break
        
        found_pods_info.append({
            "pod": pod_name,
            "status": pod_status,
            "ready": ready_status,
            "ip": pod_ip,
            "node": node_name,
            "image": image_to_display
        })
    
    if not found_pods_info:
        print_yellow("Could not extract info for any manager pods.")
        return

    # Print the results
    print_green("\n--- NetSim Pod(s) Status ---")
    for item in sorted(found_pods_info, key=lambda x: x['pod']):
        print_green(f"Pod:    {item['pod']}")
        print(f"Status: {item['status']}")
        print(f"Ready:  {item['ready']}")
        print(f"IP:     {item['ip']}")
        print(f"Node:   {item['node']}")
        print(f"Image:  {item['image']}\n")
        print_yellow("--------------------------")
    print_green("--------------------------")

def update_deployment_image(tag=None, revert=False, only=None):
    gen_script = "./scripts/gen_deployment.py"
    yaml_file = "deployment.yaml"
    backup_file = "deployment.yaml.bak"
    namespace = "sim-ns"
    
    # Centralized mapping for pod names and their corresponding image names
    pod_to_image_map = {
        "core-manager": "core-manager",
        "net-manager": "net-manager",
        "edge-manager": "core-manager",
        "clean-manager": "nettool-manager"
    }

    if revert:
        print_green("Attempting to revert image changes...")
        if not os.path.exists(backup_file):
            print_red(f"Error: Backup file '{backup_file}' not found. Cannot revert.")
            return
        
        try:
            with open(backup_file, 'r') as f:
                backup_content = f.read()
            
            print_yellow(f"\n--- Reverting to backup from '{backup_file}' ---")
            print_yellow("The following changes will be applied:")
            
            # Show diff between current and backup
            if os.path.exists(yaml_file):
                with open(yaml_file, 'r') as f:
                    current_content = f.read()
                diff = difflib.unified_diff(
                    current_content.splitlines(keepends=True),
                    backup_content.splitlines(keepends=True),
                    fromfile=yaml_file,
                    tofile=backup_file
                )
                for line in diff:
                    if line.startswith('+'):
                        print_green(line, end='')
                    elif line.startswith('-'):
                        print_red(line, end='')
                    else:
                        print(line, end='')
            else:
                print_yellow("No current deployment.yaml found to compare with. Applying backup directly.")
            
            confirm = input("\nAre you sure you want to revert? (y/n): ").lower()
            if confirm in ['y', 'yes']:
                print_green(f"Applying backup file '{backup_file}'...")
                apply_command = f"kubectl apply -f {backup_file}"
                result = subprocess.run(apply_command, shell=True, capture_output=True, text=True, check=True)
                print_green(result.stdout)
                print_green("Revert successful.")
            else:
                print_yellow("Revert cancelled.")
        except subprocess.CalledProcessError as e:
            print_red(f"Error during revert: {e.stderr}")
        except Exception as e:
            print_red(f"An unexpected error occurred during revert: {e}")
        return

    # --- Applying a new tag ---
    if not tag:
        print_red("Error: New tag must be provided for 'changeImage' action (e.g., --tag <new_tag>).")
        return

    # Filter the pod_to_image_map based on the 'only' flag
    target_pod_to_image_map = pod_to_image_map
    if only:
        print_green(f"Targeting deployment '{only}'...")
        
        target_image_name = pod_to_image_map.get(only)

        if not target_image_name:
            # fallback check
            print_red(f"Error: Could not find an image mapping for '{only}'.")
            return

        if only in ['core-manager', 'edge-manager']:
            print_yellow("Warning: 'core-manager' and 'edge-manager' share the same image; both will be updated.")
        
        target_pod_to_image_map = {}
        for deployment_keyword, image_name_value in pod_to_image_map.items():
            if image_name_value == target_image_name:
                target_pod_to_image_map[deployment_keyword] = image_name_value

    print_green(f"Generating deployment.yaml using '{gen_script}'...")
    try:
        subprocess.run(gen_script, shell=True, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print_red(f"Error generating deployment.yaml: {e.stderr}")
        return

    # Poll for the deployment.yaml
    file_found = False
    max_attempts = 3
    for attempt in range(max_attempts):
        if os.path.exists(yaml_file):
            file_found = True
            break
        
        if attempt < max_attempts - 1:
            print_yellow(f"Waiting for '{yaml_file}'... Retrying in 2 seconds. (Attempt {attempt + 1}/{max_attempts})")
            time.sleep(2)

    if not file_found:
        print_red(f"Error: '{yaml_file}' was not generated by '{gen_script}' after {max_attempts} attempts.")
        return

    print_green(f"Creating backup of '{yaml_file}' to '{backup_file}'...")
    shutil.copy(yaml_file, backup_file)

    try:
        with open(yaml_file, 'r') as f:
            original_content = f.read()

        new_content = original_content
        replacements_made_count = 0
        
        # Dynamically determine unique images and their required replacement counts from the target map
        image_replace_counts = {}
        for image_name in target_pod_to_image_map.values():
            image_replace_counts[image_name] = image_replace_counts.get(image_name, 0) + 1
        unique_image_names = list(image_replace_counts.keys())
        
        found_existing_tags = {}

        # Pass 1: Extract current tags for each unique image name
        for image_name in unique_image_names:
            pattern = re.compile(rf"{re.escape(image_name)}:([a-zA-Z0-9._-]+)")
            match = pattern.search(original_content)
            if match:
                found_existing_tags[image_name] = match.group(1)
            else:
                print_yellow(f"Warning: Image for '{image_name}' not found in deployment.yaml. Skipping replacement for this image.")

        # Pass 2: Perform targeted replacements
        print_green("Replacing image tags...")
        for image_name, replace_count in image_replace_counts.items():
            current_tag = found_existing_tags.get(image_name)
            if current_tag:
                old_image_string = f"{image_name}:{current_tag}"
                new_image_string = f"{image_name}:{tag}"
                
                # Use re.subn to replace and get the count of substitutions
                new_content, num_subs = re.subn(re.escape(old_image_string), new_image_string, new_content, count=replace_count)

                if num_subs > 0:
                    print_green(f"  -> Replaced {num_subs} instance(s) of '{image_name}' image.")
                    replacements_made_count += num_subs
                else:
                    print_yellow(f"  -> Warning: No instances of '{old_image_string}' were found to replace, though a tag was detected.")
            
        # Count Validation
        expected_replacements = len(target_pod_to_image_map) # The total number of managers being targeted
        if replacements_made_count != expected_replacements:
            print_yellow(f"Warning: Expected {expected_replacements} total replacements, but made {replacements_made_count}. Please check deployment.yaml manually.")
        else:
            print_green(f"Successfully performed {replacements_made_count} replacements.")

        # Show diff
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=yaml_file + " (original)",
            tofile=yaml_file + " (modified)"
        )
        print_yellow("\n--- Proposed Changes to deployment.yaml ---")
        has_diff = False
        for line in diff:
            has_diff = True
            if line.startswith('+'):
                print_green(line, end='')
            elif line.startswith('-'):
                print_red(line, end='')
            else:
                print(line, end='')
        if not has_diff:
            print_yellow("No changes detected. The new tag might be the same as the existing one, or the pattern was not found.")
            confirm = input("\nProceed with applying the file anyway? (y/n): ").lower()
            if confirm not in ['y', 'yes']:
                print_yellow("Operation cancelled.")
                return

        print_yellow("-------------------------------------------")

        confirm = input("\nApply these changes to the cluster? (y/n): ").lower()
        if confirm in ['y', 'yes']:
            with open(yaml_file, 'w') as f:
                f.write(new_content)
            
            print_green(f"Applying '{yaml_file}' to the cluster...")
            apply_command = f"kubectl apply -f {yaml_file}"
            result = subprocess.run(apply_command, shell=True, capture_output=True, text=True, check=True)
            print_green(result.stdout)
            print_green("Image update successful.")
        else:
            print_yellow("Image update cancelled.")
                                                                                                         
    except Exception as e:
        print_red(f"An unexpected error occurred: {e}")

def get_pod_metrics():
    namespace = "sim-ns"
    pod_to_image_map = {
        "core-manager": "core-manager",
        "net-manager": "net-manager",
        "edge-manager": "core-manager",
        "clean-manager": "nettool-manager"
    }
    target_managers = list(pod_to_image_map.keys())

    print_green(f"Fetching pod IPs for metrics in namespace: {namespace}")

    try:
        get_names_command = f"kubectl get pods -n {namespace} -o=jsonpath='{{.items[*].metadata.name}}'"
        names_result = subprocess.run(get_names_command, shell=True, capture_output=True, text=True, check=True)
        all_pod_names = names_result.stdout.split()
    except subprocess.CalledProcessError as e:
        print_red(f"Error fetching pod names: {e.stderr}")
        return

    target_pod_names = []
    for name in all_pod_names:
        for manager in target_managers:
            if manager in name:
                target_pod_names.append(name)
                break

    if not target_pod_names:
        print_yellow("No running manager pods found.")
        return

    try:
        pod_names_str = " ".join(target_pod_names)
        get_pods_command = f"kubectl get pods -n {namespace} {pod_names_str} -o json"
        pods_result = subprocess.run(get_pods_command, shell=True, capture_output=True, text=True, check=True)
        pods_data = json.loads(pods_result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print_red(f"Error fetching or parsing pod details: {e}")
        return

    pod_info_list = []
    for pod in pods_data.get("items", []):
        pod_name = pod.get("metadata", {}).get("name", "")
        pod_ip = pod.get("status", {}).get("podIP", "N/A")
        if pod_ip != "N/A":
            pod_info_list.append({"name": pod_name, "ip": pod_ip})

    if not pod_info_list:
        print_yellow("Could not retrieve IP addresses for any manager pods.")
        return

    print_green("\nSelect a pod to get metrics from:")
    for i, pod_info in enumerate(pod_info_list):
        print(f"  {i + 1}: {pod_info['name']}")
    print(f"  {len(pod_info_list) + 1}: All pods")

    try:
        choice = input(f"Enter your choice [1-{len(pod_info_list) + 1}]: ")
        choice = int(choice)
        if not (1 <= choice <= len(pod_info_list) + 1):
            print_red("Invalid choice.")
            return
    except (ValueError, KeyboardInterrupt):
        print_red("\nInvalid input or operation cancelled.")
        return

    pods_to_query = []
    if choice == len(pod_info_list) + 1:
        pods_to_query = pod_info_list
    else:
        pods_to_query.append(pod_info_list[choice - 1])

    grep_pattern = input("Optionally, enter a pattern to grep for (or press Enter to skip): ")

    for pod_info in pods_to_query:
        pod_name = pod_info['name']
        pod_ip = pod_info['ip']

        print_green(f"\n--- Metrics from {pod_name} ({pod_ip}) ---")
        
        command = f"wget -O - https://{pod_ip}:8443/metrics --no-check-certificate"
        if grep_pattern:
            grep_word = str(grep_pattern).strip()
            command += " | grep -i " + shlex.quote(grep_word)
        try:
            print_yellow(f"Executing command: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print_red(f"Error fetching metrics from {pod_name}:\n{e.stderr}")

    print_green("\n--- End of metrics ---")


def watch_pods():
    try:
        command = f"watch -n0 'kubectl get pods -n sim-ns -o wide | grep -E \"core-manager|net-manager|edge-manager|clean-manager\"'"
        subprocess.run(command, shell=True)
    except KeyboardInterrupt:
        print_red("\nExiting watch, stopped by user.")

def trace_logs(search_term, output_file=None, pod_filter=None):
    tail_lines = 50000
    print_green(f"Starting Trace for: '{search_term}'")
    
    if output_file:
        try:
            output_file = open(output_file, 'w')
            print_green(f"Writing output to file: {output_file}")
        except IOError as e:
            print_red(f"Error opening output file: {e}")
            return

    def strip_log_for_print(msg):
        print(msg)
        if output_file:
            clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', msg)
            output_file.write(clean_msg + "\n")

    print_yellow("\n--- Fetching netsim Pods ---")
    target_managers = ["core-manager", "net-manager", "edge-manager"]
    
    try:
        cmd = "kubectl get pods -n sim-ns -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName --no-headers"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        all_pods_lines = result.stdout.strip().split('\n')
    except subprocess.CalledProcessError as e:
        print_red(f"Error fetching pods: {e.stderr}")
        if output_file: output_file.close()
        return

    fetched_pods = []
    for line in all_pods_lines:
        if not line.strip(): continue
        parts = line.split()
        if len(parts) < 1: continue
        
        p_name = parts[0]
        n_name = parts[1] if len(parts) > 1 else "Pending"

        for manager in target_managers:
            if manager in p_name:
                fetched_pods.append((p_name, n_name))
                break

    if not fetched_pods:
        print_red("No manager pods found to trace.")
        if output_file: output_file.close()
        return

    pods_to_scan = []
    
    if pod_filter:
        # Flag-based selection
        for p, n in fetched_pods:
            if pod_filter in p:
                pods_to_scan.append((p, n))
        if not pods_to_scan:
            print_red(f"No pods found matching filter: '{pod_filter}'")
            if output_file: output_file.close()
            return
        print_green(f"Selected {len(pods_to_scan)} pod(s) matching '{pod_filter}'")
    else:
        # Interactive selection
        print_green(f"Found {len(fetched_pods)} manager pods.")
        print(f"  0/Enter: All Pods (Default)")
        for i, (p, n) in enumerate(fetched_pods):
            print(f"  {i+1}: {p} ({n})")
        
        try:
            selection = input("\nSelect pods to trace (e.g. '0', '1', '1,3', '1-3'): ").strip()
        except KeyboardInterrupt:
            print_yellow("\nOperation cancelled.")
            if output_file: output_file.close()
            return

        if not selection or selection == '0':
            pods_to_scan = fetched_pods
        else:
            try:
                indices = set()
                parts = selection.split(',')
                for part in parts:
                    if '-' in part:
                        range_parts = part.split('-')
                        start = int(range_parts[0])
                        end = int(range_parts[1])
                        for k in range(start, end + 1):
                            indices.add(k)
                    else:
                        indices.add(int(part))
                
                for i in indices:
                    if 1 <= i <= len(fetched_pods):
                        pods_to_scan.append(fetched_pods[i-1])
                    else:
                        print_yellow(f"Warning: Index {i} out of range, skipping.")
            except ValueError:
                print_red("Invalid selection format. Defaulting to All Pods.")
                pods_to_scan = fetched_pods

    if not pods_to_scan:
        print_red("No pods selected.")
        if output_file: output_file.close()
        return

    print_green(f"Scanning {len(pods_to_scan)} pod(s)...")
    print_yellow(f"\n--- Scanning Logs for '{search_term}' ---")
    
    total_matches = 0
    error_logs = []
    
    def is_error_log(log_line):
        if '"level":"error"' in log_line or '"level":"err"' in log_line:
            return True
        if '"level":"info"' in log_line or '"level":"debug"' in log_line or '"level":"warn"' in log_line:
            return False
            
        if re.search(r'(level|lvl)=(error|err)', log_line, re.IGNORECASE):
            return True
        if re.search(r'\[(error|err)\]', log_line, re.IGNORECASE):
            return True
            
        return False

    for pod_name, node_name in pods_to_scan:
        container_name = ""
        if "core-manager" in pod_name: container_name = "core-manager"
        elif "edge-manager" in pod_name: container_name = "edge-manager"
        elif "net-manager" in pod_name: container_name = "net-manager"

        print(f"\nScanning \033[95m{pod_name}\033[0m ... ", end='', flush=True)
        
        try:
            log_cmd = f"kubectl logs {pod_name} -c {container_name} -n sim-ns --timestamps --tail={tail_lines}"
            log_result = subprocess.run(log_cmd, shell=True, capture_output=True, text=True, errors='replace')
            
            if log_result.returncode != 0:
                print_red(f"[Failed] {log_result.stderr.strip()}")
                continue

            logs = log_result.stdout.splitlines()
            
            matches = []
            lower_search_term = search_term.lower()
            
            for line in logs:
                if lower_search_term in line.lower():
                    matches.append(line)
            
            if len(matches) > 0:
                print_green(f"[Found {len(matches)} matches]")
                
                for line in matches:
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2:
                        timestamp, message = parts
                        try:
                            clean_ts = timestamp.split('.')[0].replace('T', ' ')
                        except:
                            clean_ts = timestamp
                        
                        msg_colored = re.sub(re.escape(search_term), f"\033[91;1m{search_term}\033[0m", message, flags=re.IGNORECASE)
                        
                        formatted_line = f"[\033[95m{pod_name}\033[0m|\033[95m{node_name}\033[0m] \033[93m{clean_ts}\033[0m {msg_colored}"
                        strip_log_for_print(formatted_line)
                        
                        if is_error_log(message):
                            error_logs.append(formatted_line)
                    else:
                        msg_colored = re.sub(re.escape(search_term), f"\033[91;1m{search_term}\033[0m", line.strip(), flags=re.IGNORECASE)
                        formatted_line = f"[\033[95m{pod_name}\033[0m|\033[95m{node_name}\033[0m] {msg_colored}"
                        strip_log_for_print(formatted_line)
                        
                        if is_error_log(line):
                            error_logs.append(formatted_line)

                strip_log_for_print("")
                total_matches += len(matches)
            else:
                print("No matches.")
                
        except Exception as e:
            print_red(f"[Error] {e}")

    strip_log_for_print("\n--- Trace Complete ---")
    strip_log_for_print(f"Total matching lines found: {total_matches}")

    if error_logs:
        strip_log_for_print("\n--- Error Summary ---")
        for log in error_logs:
            strip_log_for_print(log)
    else:
        strip_log_for_print("\nNo error logs found containing the search term.")
    
    if output_file:
        output_file.close()
        