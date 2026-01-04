#!/bin/bash
set -e

# TubeArchivist Plex Integration Installer
# Usage: curl -sSL https://raw.githubusercontent.com/tubearchivist/tubearchivist-plex/main/install.sh | bash
# 
# Environment variables (optional):
#   PLEX_DIR - Plex Media Server directory path
#   TA_URL - TubeArchivist URL (default: http://localhost:8000)
#   TA_API_KEY - TubeArchivist API Key
#   PLEX_USER - Plex service user for file ownership
#   PLEX_GROUP - Plex service group for file ownership
#   DRY_RUN - Set to 1 for dry-run mode (validation only, no changes)

REPO_URL="https://github.com/tubearchivist/tubearchivist-plex"
DOWNLOAD_URL="${REPO_URL}/archive/refs/heads/main.zip"
TEMP_DIR=$(mktemp -d)
BUNDLE_NAME="TubeArchivist-Agent.bundle"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
dry_run() { echo -e "${YELLOW}[DRY-RUN]${NC} $1"; }

# Cleanup on exit
trap 'rm -rf "$TEMP_DIR" 2>/dev/null || true' EXIT

# Check dependencies
check_deps() {
    command -v curl >/dev/null 2>&1 || error "curl is required"
    command -v unzip >/dev/null 2>&1 || error "unzip is required"
    if ! command -v jq >/dev/null 2>&1; then
        warn "jq not found - will use sed for JSON editing"
    fi
}

# Get input with env var fallback
get_input() {
    local prompt="$1"
    local var_name="$2"
    local default="$3"
    
    if [[ -n "${!var_name:-}" ]]; then
        log "Using $var_name: ${!var_name}"
        return 0
    fi
    
    if [[ -n "$default" ]]; then
        read -p "$prompt [$default]: " input
        eval "$var_name=\"\${input:-$default}\""
    else
        read -p "$prompt: " input
        eval "$var_name=\"$input\""
    fi
}

# Main installation
main() {
    log "TubeArchivist Plex Integration Installer"
    
    if [[ "${DRY_RUN:-}" == "1" ]]; then
        warn "DRY-RUN MODE: No changes will be made"
    fi
    
    check_deps
    
    # Get Plex directory
    get_input "Plex Media Server directory path" "PLEX_DIR" ""
    [[ -d "$PLEX_DIR" ]] || error "Directory does not exist: $PLEX_DIR"
    [[ -w "$PLEX_DIR" ]] || error "Directory is not writable: $PLEX_DIR"
    
    # Check for existing installation
    CONFIG_FILE="$PLEX_DIR/Scanners/Series/ta_config.json"
    if [[ -f "$CONFIG_FILE" ]]; then
        log "Existing installation detected - performing update"
        if [[ "${DRY_RUN:-}" != "1" ]]; then
            cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%s)"
            log "Backed up existing config"
        else
            dry_run "Would backup existing config"
        fi
        
        # Read existing config
        if command -v jq >/dev/null 2>&1; then
            EXISTING_URL=$(jq -r '.TA_URL // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
            EXISTING_KEY=$(jq -r '.TA_TOKEN // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
        else
            EXISTING_URL=$(grep -o '"TA_URL": *"[^"]*"' "$CONFIG_FILE" 2>/dev/null | cut -d'"' -f4 || echo "")
            EXISTING_KEY=$(grep -o '"TA_TOKEN": *"[^"]*"' "$CONFIG_FILE" 2>/dev/null | cut -d'"' -f4 || echo "")
        fi
        
        # Use existing values as defaults
        [[ -z "${TA_URL:-}" && -n "$EXISTING_URL" ]] && TA_URL="$EXISTING_URL"
        [[ -z "${TA_API_KEY:-}" && -n "$EXISTING_KEY" ]] && TA_API_KEY="$EXISTING_KEY"
    fi
    
    # Get TubeArchivist config
    get_input "TubeArchivist URL" "TA_URL" "http://localhost:8000"
    get_input "TubeArchivist API Key" "TA_API_KEY" ""
    [[ -n "$TA_API_KEY" ]] || error "API Key is required"
    
    # Get ownership info
    if [[ -z "${PLEX_USER:-}" || -z "${PLEX_GROUP:-}" ]]; then
        # Try to detect ownership, fallback to empty if fails
        DETECTED_USER=""
        DETECTED_GROUP=""
        if [[ -d "$PLEX_DIR" ]]; then
            DETECTED_USER=$(stat -c '%U' "$PLEX_DIR" 2>/dev/null || stat -f '%Su' "$PLEX_DIR" 2>/dev/null || echo "")
            DETECTED_GROUP=$(stat -c '%G' "$PLEX_DIR" 2>/dev/null || stat -f '%Sg' "$PLEX_DIR" 2>/dev/null || echo "")
        fi
        
        get_input "Plex user for file ownership" "PLEX_USER" "$DETECTED_USER"
        get_input "Plex group for file ownership" "PLEX_GROUP" "$DETECTED_GROUP"
    fi
    
    # Download and install
    log "Downloading TubeArchivist Plex integration..."
    if [[ "${DRY_RUN:-}" == "1" ]]; then
        dry_run "Would download: $DOWNLOAD_URL"
        dry_run "Would extract and rename to: $BUNDLE_NAME"
    else
        cd "$TEMP_DIR"
        curl -sSL "$DOWNLOAD_URL" -o main.zip
        unzip -q main.zip
        mv tubearchivist-plex-main "$BUNDLE_NAME"
    fi
    
    # Install Scanner
    log "Installing Scanner..."
    SCANNERS_DIR="$PLEX_DIR/Scanners"
    if [[ "${DRY_RUN:-}" == "1" ]]; then
        dry_run "Would install scanner to: $SCANNERS_DIR"
        dry_run "Would configure: $SCANNERS_DIR/Series/ta_config.json"
        dry_run "Would set TA_URL: $TA_URL"
        dry_run "Would set TA_TOKEN: [REDACTED]"
    else
        mkdir -p "$SCANNERS_DIR"
        cp -r "$BUNDLE_NAME/Scanners/"* "$SCANNERS_DIR/"
        
        # Configure scanner
        CONFIG_FILE="$SCANNERS_DIR/Series/ta_config.json"
        [[ ! -f "$CONFIG_FILE" ]] && cp "$SCANNERS_DIR/Series/sample-ta_config.json" "$CONFIG_FILE"
        
        if command -v jq >/dev/null 2>&1; then
            jq --arg url "$TA_URL" --arg key "$TA_API_KEY" \
               '.TA_URL = $url | .TA_TOKEN = $key' "$CONFIG_FILE" > "$CONFIG_FILE.tmp"
            mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
        else
            sed -i.bak "s|\"TA_URL\": \".*\"|\"TA_URL\": \"$TA_URL\"|" "$CONFIG_FILE"
            sed -i.bak "s|\"TA_TOKEN\": \".*\"|\"TA_TOKEN\": \"$TA_API_KEY\"|" "$CONFIG_FILE"
            rm -f "$CONFIG_FILE.bak"
        fi
    fi
    
    # Install Agent
    log "Installing Agent..."
    PLUGINS_DIR="$PLEX_DIR/Plug-ins"
    if [[ "${DRY_RUN:-}" == "1" ]]; then
        dry_run "Would install agent to: $PLUGINS_DIR/$BUNDLE_NAME"
    else
        mkdir -p "$PLUGINS_DIR"
        rm -rf "$BUNDLE_NAME/Scanners"
        cp -r "$BUNDLE_NAME" "$PLUGINS_DIR/"
    fi
    
    # Set permissions
    if [[ -n "${PLEX_USER:-}" && -n "${PLEX_GROUP:-}" ]]; then
        if [[ "${DRY_RUN:-}" == "1" ]]; then
            dry_run "Would set ownership to $PLEX_USER:$PLEX_GROUP"
        else
            log "Setting permissions to $PLEX_USER:$PLEX_GROUP..."
            if chown -R "$PLEX_USER:$PLEX_GROUP" "$SCANNERS_DIR" "$PLUGINS_DIR/$BUNDLE_NAME" 2>/dev/null; then
                log "Permissions set successfully"
            else
                warn "Could not set ownership. You may need to fix permissions manually."
            fi
        fi
    fi
    
    # Completion message
    log "Installation complete!"
    if [[ "${DRY_RUN:-}" == "1" ]]; then
        warn "DRY-RUN MODE: No actual changes were made"
        log "Validation completed successfully"
    else
        echo
        log "Next steps:"
        echo "1. Restart Plex Media Server"
        echo "2. Create/edit a TV Shows library"
        echo "3. Set Scanner to 'TubeArchivist Scanner'"
        echo "4. Set Agent to 'TubeArchivist Agent'"
        echo "5. Configure Agent with your API Key and URL: $TA_URL"
    fi
}

main "$@"
