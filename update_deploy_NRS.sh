#!/bin/bash

# Script to update deploy_NRS.sh with the latest versions from the required files for the Network Resource Simulator

SOURCE_DIR="./" #Update as required

# Required files
REQUIRED_FILES=(
    "netsim.py"
    "resourceGen.py"
    "cachetime.py"
    "manipulation.py"
    "template.json"
    "pods.py"
    "utils.py"
    "README.md"
)

TARGET_SCRIPT="../deploy_NRS.sh"

check_files() {
    local missing=0
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$SOURCE_DIR/$file" ]; then
            echo "Error: Required file '$file' not found in $SOURCE_DIR"
            missing=1
        fi
    done
    
    if [ $missing -eq 1 ]; then
        echo "Some required files are missing. Aborting."
        exit 1
    fi
    
    echo "  --      All required files found."
}

backup_script() {
    local backup_file="${TARGET_SCRIPT}.bak"
    cp "$TARGET_SCRIPT" "$backup_file"
    echo "  --      Backup created at $backup_file"
}

update_script() {
    local temp_file=$(mktemp)
    
    # Write the known header directly
    cat > "$temp_file" << 'HEADER'
#!/bin/bash

# Check for write permissions in the current directory before proceeding.
# This ensures the 'networkResourceSimulator' directory can be created locally.
if [ ! -w . ]; then
    echo "Error: You do not have write permissions in the current directory ($(pwd))."
    echo "Please run this script from a directory where you have write permissions."
    exit 1
fi

# This will be created in the user's current working directory.
TARGET_DIR="./networkResourceSimulator"

if [ -d "$TARGET_DIR" ]; then
    echo "Warning: $TARGET_DIR already exists."
    read -p "Do you want to overwrite it? (y/n): " choice
    if [ "$choice" == "y" ] || [ "$choice" == "Y" ]; then
        rm -rf "$TARGET_DIR"
    else
        echo "Exiting without changes."
        exit 1
    fi
fi

echo -e "\n Deploying Network Resource Simulator..."

if [ -d "$TARGET_DIR" ]; then
    cd $TARGET_DIR
else
    mkdir -p $TARGET_DIR
    cd $TARGET_DIR
fi

echo -e "\n Directory 'networkResourceSimulator' created."

echo -e "\n Creating files:"
HEADER
    
    cat >> "$temp_file" << EOL
echo "   - manipulation.py"
cat >manipulation.py <<'EOF'
$(cat "$SOURCE_DIR/manipulation.py")
EOF

echo "   - resourceGen.py"
cat >resourceGen.py <<'EOF'
$(cat "$SOURCE_DIR/resourceGen.py")
EOF

echo "   - template.json"
cat >template.json <<'EOF'
$(cat "$SOURCE_DIR/template.json")
EOF

echo "   - cachetime.py"
cat >cachetime.py <<'EOF'
$(cat "$SOURCE_DIR/cachetime.py")
EOF

echo "   - netsim.py"
cat >netsim.py <<'EOF'
$(cat "$SOURCE_DIR/netsim.py")
EOF

echo "   - README.md"
cat >README.md <<'EOF'
$(cat "$SOURCE_DIR/README.md")
EOF

echo "   - utils.py"
cat >utils.py <<'EOF'
$(cat "$SOURCE_DIR/utils.py")
EOF

echo "   - pods.py"
cat >pods.py <<'EOF'
$(cat "$SOURCE_DIR/pods.py")
EOF

echo -e "\n Making 'netsim.py' executable..."
chmod +x netsim.py

echo -e "\nThe Network Resource Simulator is ready for use."

echo -e "\nStarter guide:"
echo "1. Change into the new directory:"
echo "   cd networkResourceSimulator"
echo
echo "2. Run the simulator to see available commands:"
echo "   ./netsim.py"
echo
echo "3. Or, create and apply your first VPC:"
echo "   ./netsim.py create -a"
EOL

    mv "$temp_file" "$TARGET_SCRIPT"
    chmod +x "$TARGET_SCRIPT"
    
    echo "  --      Script updated successfully with the latest file contents."
}

main() {
    echo "Updating NRS..."
    echo ""
    echo "  --      Checking for required files..."
    check_files
    
    echo "  --      Creating backup of original script..."
    backup_script
    
    echo "  --      Updating script with latest file contents..."
    update_script

    echo ""
    echo "Done! The deploy_NRS.sh has been updated with the latest versions of code from all required files."
}

main