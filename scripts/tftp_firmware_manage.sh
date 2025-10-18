#!/bin/bash
# TFTP Firmware Manager for U-Boot Recovery
# ==========================================
# Manages firmware images in TFTP server for device recovery operations.
#
# Features:
# - Upload firmware images to TFTP directory
# - List available images with metadata
# - Verify checksums (SHA256)
# - Set symlinks for device-specific bootfiles
# - Clean up old/unused images
#
# Usage:
#   ./tftp_firmware_manager.sh upload <image_path> [--device <device_name>]
#   ./tftp_firmware_manager.sh list
#   ./tftp_firmware_manager.sh link <image_name> <bootfile_name>
#   ./tftp_firmware_manager.sh verify <image_name>
#   ./tftp_firmware_manager.sh clean [--older-than <days>]

set -e

# Configuration
TFTP_ROOT="${HIL_TFTP_ROOT:-/srv/tftp}"
TFTP_USER="${TFTP_USER:-tftp}"
METADATA_DIR="$TFTP_ROOT/.metadata"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════════"
    echo ""
}

# Check if TFTP server is accessible
check_tftp_server() {
    if [ ! -d "$TFTP_ROOT" ]; then
        print_error "TFTP root directory not found: $TFTP_ROOT"
        print_info "Run setup_tftp_server.sh first or set HIL_TFTP_ROOT environment variable"
        exit 1
    fi

    if ! systemctl is-active --quiet tftpd-hpa; then
        print_warning "TFTP server (tftpd-hpa) is not running"
        print_info "Start it with: sudo systemctl start tftpd-hpa"
    fi

    # Ensure metadata directory exists
    sudo mkdir -p "$METADATA_DIR"
    sudo chown -R "$TFTP_USER:$TFTP_USER" "$METADATA_DIR" 2>/dev/null || true
}

# Calculate SHA256 checksum
calculate_sha256() {
    local file="$1"
    sha256sum "$file" | awk '{print $1}'
}

# Get human-readable file size
get_file_size() {
    local file="$1"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        stat -f%z "$file" | numfmt --to=iec-i --suffix=B
    else
        stat --format=%s "$file" | numfmt --to=iec-i --suffix=B
    fi
}

# Upload firmware image to TFTP
cmd_upload() {
    local image_path="$1"
    local device_name="${2:-unknown}"

    if [ ! -f "$image_path" ]; then
        print_error "Image file not found: $image_path"
        exit 1
    fi

    print_header "Uploading Firmware to TFTP"

    local image_basename=$(basename "$image_path")
    local dest_path="$TFTP_ROOT/$image_basename"
    local metadata_file="$METADATA_DIR/${image_basename}.meta"

    print_info "Source: $image_path"
    print_info "Destination: $dest_path"
    print_info "Device: $device_name"

    # Calculate checksum before upload
    print_info "Calculating SHA256 checksum..."
    local sha256=$(calculate_sha256 "$image_path")
    local file_size=$(get_file_size "$image_path")

    print_info "SHA256: $sha256"
    print_info "Size: $file_size"

    # Copy to TFTP directory
    print_info "Copying to TFTP directory..."
    sudo cp "$image_path" "$dest_path"
    sudo chown "$TFTP_USER:$TFTP_USER" "$dest_path"
    sudo chmod 644 "$dest_path"

    # Verify upload
    print_info "Verifying upload integrity..."
    local dest_sha256=$(calculate_sha256 "$dest_path")

    if [ "$sha256" != "$dest_sha256" ]; then
        print_error "Checksum mismatch! Upload may be corrupted."
        sudo rm "$dest_path"
        exit 1
    fi

    # Save metadata
    print_info "Saving metadata..."
    sudo tee "$metadata_file" > /dev/null <<EOF
# Metadata for $image_basename
upload_date=$(date -Iseconds)
device=$device_name
sha256=$sha256
size_bytes=$(stat --format=%s "$image_path" 2>/dev/null || stat -f%z "$image_path")
size_human=$file_size
source_path=$image_path
EOF
    sudo chown "$TFTP_USER:$TFTP_USER" "$metadata_file"

    print_success "Firmware uploaded successfully!"
    print_info "TFTP bootfile path: $image_basename"

    # Show U-Boot command example
    echo ""
    print_info "Example U-Boot commands:"
    echo "  setenv serverip <TFTP_SERVER_IP>"
    echo "  setenv ipaddr <DEVICE_IP>"
    echo "  setenv bootfile $image_basename"
    echo "  tftpboot 0x4007ff28"
    echo "  bootm 0x4007ff28"
}

# List all firmware images in TFTP
cmd_list() {
    print_header "Available Firmware Images in TFTP"

    if [ ! -d "$TFTP_ROOT" ]; then
        print_error "TFTP directory not found: $TFTP_ROOT"
        exit 1
    fi

    local count=0

    # Find all firmware-like files (common extensions)
    while IFS= read -r -d '' file; do
        local basename=$(basename "$file")
        local metadata_file="$METADATA_DIR/${basename}.meta"

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${GREEN}📦 $basename${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # Show basic info
        local size=$(get_file_size "$file")
        local modified=$(stat --format='%y' "$file" 2>/dev/null | cut -d'.' -f1 || stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$file")

        echo "  Path:     $file"
        echo "  Size:     $size"
        echo "  Modified: $modified"

        # Show metadata if available
        if [ -f "$metadata_file" ]; then
            while IFS= read -r line; do
                if [[ ! "$line" =~ ^# ]] && [[ -n "$line" ]]; then
                    local key=$(echo "$line" | cut -d'=' -f1)
                    local value=$(echo "$line" | cut -d'=' -f2-)
                    case "$key" in
                        device) echo "  Device:   $value" ;;
                        sha256) echo "  SHA256:   $value" ;;
                        upload_date) echo "  Uploaded: $value" ;;
                    esac
                fi
            done < "$metadata_file"
        fi

        # Check for symlinks pointing to this file
        local symlinks=$(find "$TFTP_ROOT" -maxdepth 1 -type l -exec sh -c 'readlink "$1" | grep -q "'"$basename"'" && echo "$(basename "$1")"' _ {} \;)
        if [ -n "$symlinks" ]; then
            echo "  Symlinks: $symlinks"
        fi

        count=$((count + 1))
    done < <(find "$TFTP_ROOT" -maxdepth 1 -type f \( -name "*.bin" -o -name "*.itb" -o -name "*.img" -o -name "*.elf" \) -print0 | sort -z)

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "Found $count firmware image(s)"
}

# Create symlink for bootfile
cmd_link() {
    local image_name="$1"
    local link_name="$2"

    if [ -z "$image_name" ] || [ -z "$link_name" ]; then
        print_error "Usage: $0 link <image_name> <bootfile_name>"
        exit 1
    fi

    local image_path="$TFTP_ROOT/$image_name"
    local link_path="$TFTP_ROOT/$link_name"

    if [ ! -f "$image_path" ]; then
        print_error "Image not found: $image_name"
        exit 1
    fi

    print_info "Creating symlink: $link_name -> $image_name"

    # Remove existing symlink if it exists
    if [ -L "$link_path" ]; then
        sudo rm "$link_path"
        print_warning "Removed existing symlink"
    fi

    sudo ln -s "$image_name" "$link_path"
    sudo chown -h "$TFTP_USER:$TFTP_USER" "$link_path"

    print_success "Symlink created successfully"
    print_info "U-Boot bootfile: $link_name"
}

# Verify image checksum
cmd_verify() {
    local image_name="$1"

    if [ -z "$image_name" ]; then
        print_error "Usage: $0 verify <image_name>"
        exit 1
    fi

    local image_path="$TFTP_ROOT/$image_name"
    local metadata_file="$METADATA_DIR/${image_name}.meta"

    if [ ! -f "$image_path" ]; then
        print_error "Image not found: $image_name"
        exit 1
    fi

    print_header "Verifying Firmware Image"
    print_info "Image: $image_name"

    # Calculate current checksum
    print_info "Calculating SHA256..."
    local current_sha256=$(calculate_sha256 "$image_path")
    echo "  Current: $current_sha256"

    # Compare with stored metadata
    if [ -f "$metadata_file" ]; then
        local stored_sha256=$(grep '^sha256=' "$metadata_file" | cut -d'=' -f2)
        echo "  Stored:  $stored_sha256"

        if [ "$current_sha256" = "$stored_sha256" ]; then
            print_success "Checksum verification PASSED"
        else
            print_error "Checksum verification FAILED"
            print_warning "Image may be corrupted or modified"
            exit 1
        fi
    else
        print_warning "No metadata found, cannot verify against original"
        print_info "Current SHA256: $current_sha256"
    fi
}

# Clean up old images
cmd_clean() {
    local days="${1:-30}"

    print_header "Cleaning Up Old Firmware Images"
    print_info "Removing images older than $days days"

    local count=0

    while IFS= read -r -d '' file; do
        local basename=$(basename "$file")
        local metadata_file="$METADATA_DIR/${basename}.meta"

        print_info "Removing: $basename"
        sudo rm "$file"

        if [ -f "$metadata_file" ]; then
            sudo rm "$metadata_file"
        fi

        count=$((count + 1))
    done < <(find "$TFTP_ROOT" -maxdepth 1 -type f \( -name "*.bin" -o -name "*.itb" -o -name "*.img" \) -mtime "+$days" -print0)

    if [ $count -eq 0 ]; then
        print_success "No old images to clean"
    else
        print_success "Removed $count image(s)"
    fi
}

# Show usage
cmd_usage() {
    cat <<EOF
TFTP Firmware Manager - Manage firmware images for U-Boot recovery

Usage:
  $0 upload <image_path> [--device <device_name>]
      Upload a firmware image to TFTP server

  $0 list
      List all available firmware images with metadata

  $0 link <image_name> <bootfile_name>
      Create a symlink for device-specific bootfile names

  $0 verify <image_name>
      Verify firmware image checksum integrity

  $0 clean [--older-than <days>]
      Remove firmware images older than specified days (default: 30)

  $0 help
      Show this help message

Environment Variables:
  HIL_TFTP_ROOT    TFTP server root directory (default: /srv/tftp)

Examples:
  # Upload a firmware image
  $0 upload /path/to/firmware.itb --device belkin_rt3200

  # List all images
  $0 list

  # Create symlink for U-Boot bootfile
  $0 link firmware-v1.2.3.itb recovery.itb

  # Verify image integrity
  $0 verify firmware-v1.2.3.itb

  # Clean up images older than 60 days
  $0 clean --older-than 60

EOF
}

# Main command dispatcher
main() {
    check_tftp_server

    local command="${1:-help}"
    shift || true

    case "$command" in
        upload)
            local image_path="$1"
            shift || true
            local device_name="unknown"

            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --device)
                        device_name="$2"
                        shift 2
                        ;;
                    *)
                        shift
                        ;;
                esac
            done

            cmd_upload "$image_path" "$device_name"
            ;;
        list)
            cmd_list
            ;;
        link)
            cmd_link "$1" "$2"
            ;;
        verify)
            cmd_verify "$1"
            ;;
        clean)
            local days=30
            if [ "$1" = "--older-than" ]; then
                days="$2"
            fi
            cmd_clean "$days"
            ;;
        help|--help|-h)
            cmd_usage
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            cmd_usage
            exit 1
            ;;
    esac
}

# Run main
main "$@"
